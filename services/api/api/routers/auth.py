"""SPEC "Accounts and anonymity", protocol steps 1-6 (decision 5: email + password)."""

import datetime as dt
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import codes
from api.auth.account_data import account_out
from api.auth.emails import (
    EmailBackend,
    EmailKind,
    OutgoingEmail,
    get_email_backend,
    normalize_uchicago_email,
)
from api.auth.passwords import hash_password, needs_rehash, verify_password
from api.auth.ratelimit import (
    EMAIL_START_PER_ADDRESS,
    LOGIN_FAILURES,
    RESET_START_PER_ADDRESS,
    account_subject,
    email_subject,
    ip_limit,
    login_subject,
)
from api.auth.sessions import (
    SessionData,
    clear_session_cookie,
    cookie_name,
    create_session,
    current_account,
    destroy_account_sessions,
    destroy_session,
    load_session,
    optional_session,
    require_session,
    set_session_cookie,
)
from api.auth.store import Store, get_store
from api.db.models import Account
from api.db.session import get_session
from api.schemas.auth import (
    EmailStart,
    EmailStarted,
    Login,
    PasswordResetFinish,
    PasswordResetStart,
    Register,
    RegistrationTicket,
    SessionOut,
    VerifyCode,
)
from api.schemas.common import NOT_IMPLEMENTED

router = APIRouter(prefix="/auth", tags=["auth"], responses=NOT_IMPLEMENTED)

BAD_LOGIN = "Wrong username, email or password."


def _start_session(
    request: Request, response: Response, store: Store, account: Account
) -> SessionOut:
    """Always a fresh session id; a session the browser already had is ended (no fixation)."""
    old_sid = request.cookies.get(cookie_name())
    if old_sid and (old := load_session(store, old_sid)):
        destroy_session(store, old)
    session = create_session(store, account.id)
    set_session_cookie(response, session)
    return SessionOut(account=account_out(account), csrf_token=session.csrf_token)


@router.post(
    "/email",
    response_model=EmailStarted,
    status_code=202,
    dependencies=[Depends(ip_limit("email-start", 40))],
)
def start_email(
    body: EmailStart,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
    mailer: Annotated[EmailBackend, Depends(get_email_backend)],
) -> EmailStarted:
    email = normalize_uchicago_email(body.email)
    if email is None:
        raise HTTPException(status_code=400, detail="Use your @uchicago.edu email address.")
    EMAIL_START_PER_ADDRESS.hit(store, email_subject(email))
    taken = db.scalar(sa.select(Account.id).where(Account.email == email)) is not None
    # Same response either way: only the mailbox owner learns whether an account exists.
    pending_id, code = codes.create_pending(
        store, "signup", None if taken else email, address=email
    )
    kind: EmailKind = "already_registered" if taken else "signup_code"
    background.add_task(
        mailer.send, OutgoingEmail(to=email, kind=kind, pending_id=pending_id, code=code)
    )
    return EmailStarted(pending_id=pending_id)


@router.post(
    "/verify-code",
    response_model=RegistrationTicket,
    dependencies=[Depends(ip_limit("verify-code", 100))],
)
def verify_code(
    body: VerifyCode, store: Annotated[Store, Depends(get_store)]
) -> RegistrationTicket:
    email = codes.redeem_pending(store, "signup", body.pending_id, body.code)
    return RegistrationTicket(ticket=codes.create_ticket(store, email))


@router.post(
    "/register",
    response_model=SessionOut,
    status_code=201,
    dependencies=[Depends(ip_limit("register", 40))],
)
def register(
    body: Register,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionOut:
    email = codes.peek_ticket(store, body.ticket)
    if email is None:
        raise HTTPException(
            status_code=400, detail="Your email verification has expired. Start again."
        )
    username_taken = HTTPException(status_code=409, detail="That username is taken.")
    by_username = sa.select(Account.id).where(
        sa.func.lower(Account.username) == body.username.lower()
    )
    if db.scalar(by_username) is not None:
        raise username_taken
    account = Account(
        username=body.username,
        email=email,
        email_verified_day=dt.datetime.now(dt.UTC).date(),
        password_hash=hash_password(body.password),
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request won the username or the email (one account per email).
        db.rollback()
        if db.scalar(by_username) is not None:
            raise username_taken from None
        codes.delete_ticket(store, body.ticket)
        raise HTTPException(
            status_code=409,
            detail="This email already has an account. Log in or reset your password.",
        ) from None
    codes.delete_ticket(store, body.ticket)
    db.refresh(account)
    return _start_session(request, response, store, account)


@router.post("/login", response_model=SessionOut, dependencies=[Depends(ip_limit("login", 300))])
def login(
    body: Login,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionOut:
    ident = body.login.strip().lower()
    # Count the attempt before the (slow) password check and give it back on success, so
    # concurrent wrong guesses cannot all pass a check made before any of them was recorded.
    subjects = [login_subject(ident)]
    LOGIN_FAILURES.hit(store, subjects[0])
    if "@" in ident:
        query = sa.select(Account).where(Account.email == ident)
    else:
        query = sa.select(Account).where(sa.func.lower(Account.username) == ident)
    account = db.scalar(query)
    if account is not None:
        # One budget per account, however it is named (username or email).
        subjects.append(account_subject(account.id))
        LOGIN_FAILURES.hit(store, subjects[1])
    if not verify_password(account.password_hash if account else None, body.password):
        raise HTTPException(status_code=401, detail=BAD_LOGIN)
    assert account is not None and account.password_hash is not None
    for subject in subjects:
        LOGIN_FAILURES.refund(store, subject)
    if needs_rehash(account.password_hash):
        account.password_hash = hash_password(body.password)
        db.commit()
        db.refresh(account)
    return _start_session(request, response, store, account)


@router.post(
    "/logout",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(ip_limit("logout", 600))],
)
def logout(
    response: Response,
    session: Annotated[SessionData | None, Depends(optional_session)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    if session is not None:
        destroy_session(store, session)
    clear_session_cookie(response)


@router.get(
    "/session", response_model=SessionOut, dependencies=[Depends(ip_limit("session", 20000))]
)
def current_session(
    response: Response,
    session: Annotated[SessionData, Depends(require_session)],
    account: Annotated[Account, Depends(current_account)],
) -> SessionOut:
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(account=account_out(account), csrf_token=session.csrf_token)


@router.post(
    "/password-reset/start",
    response_model=EmailStarted,
    status_code=202,
    dependencies=[Depends(ip_limit("reset-start", 40))],
)
def start_password_reset(
    body: PasswordResetStart,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
    mailer: Annotated[EmailBackend, Depends(get_email_backend)],
) -> EmailStarted:
    # Always 202 with a pending id; a code is emailed only if the account exists.
    email = normalize_uchicago_email(body.email)
    address = email or body.email.strip().lower()
    RESET_START_PER_ADDRESS.hit(store, email_subject(address))
    exists = (
        email is not None
        and db.scalar(sa.select(Account.id).where(Account.email == email)) is not None
    )
    pending_id, code = codes.create_pending(
        store, "reset", email if exists else None, address=address
    )
    if email is not None and exists:
        background.add_task(
            mailer.send,
            OutgoingEmail(to=email, kind="reset_code", pending_id=pending_id, code=code),
        )
    return EmailStarted(pending_id=pending_id)


@router.post(
    "/password-reset/finish",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(ip_limit("reset-finish", 100))],
)
def finish_password_reset(
    body: PasswordResetFinish,
    response: Response,
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    email = codes.redeem_pending(store, "reset", body.pending_id, body.code)
    account = db.scalar(sa.select(Account).where(Account.email == email))
    if account is None:  # deleted in the last ten minutes
        raise HTTPException(status_code=400, detail=codes.INVALID_CODE)
    account.password_hash = hash_password(body.new_password)
    db.commit()
    # Whoever reset the password has no session yet, so "other sessions" is all of them.
    destroy_account_sessions(store, account.id)
    clear_session_cookie(response)
