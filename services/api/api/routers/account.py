"""`/account`: export, change password, delete (SPEC "Account deletion")."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from api.agents.interview import welcome_key
from api.auth import account_data
from api.auth.account_data import account_out, export_plans
from api.auth.passwords import hash_password, verify_password
from api.auth.ratelimit import PASSWORD_FAILURES, account_subject, ip_limit
from api.auth.sessions import (
    SessionData,
    clear_session_cookie,
    current_account,
    destroy_account_sessions,
    require_session,
)
from api.auth.store import Store, get_store
from api.db.models import Account
from api.db.session import get_session
from api.forum.admin import upheld_removals
from api.schemas.auth import AccountDelete, AccountExport, PasswordChange
from api.schemas.common import NOT_IMPLEMENTED

router = APIRouter(prefix="/account", tags=["account"], responses=NOT_IMPLEMENTED)


def _confirm_password(store: Store, account: Account, password: str) -> None:
    """Re-authentication for sensitive actions, with its own per-account failure limit."""
    subject = account_subject(account.id)
    # Counted before the (slow) check and given back on success, so concurrent wrong guesses
    # cannot all pass a check made before any of them was recorded.
    PASSWORD_FAILURES.hit(store, subject)
    # The frozen schemas put no length cap on these fields; do not hash huge inputs.
    if len(password) > 256 or not verify_password(account.password_hash, password):
        raise HTTPException(status_code=403, detail="That password is wrong.")
    PASSWORD_FAILURES.refund(store, subject)


def _refuse_while_restricted(account: Account) -> None:
    """Deleting frees the email for a new account, so it must not be a way out of a ban or a
    suspension. Day-level, like every date kept about a user."""
    today = dt.datetime.now(dt.UTC).date()
    suspended = account.suspended_until is not None and account.suspended_until > today
    if account.status != "active" or suspended:
        raise HTTPException(
            status_code=409,
            detail="This account is restricted, so it cannot be deleted right now.",
        )


@router.get(
    "/export", response_model=AccountExport, dependencies=[Depends(ip_limit("export", 600))]
)
def export_account(
    response: Response,
    account: Annotated[Account, Depends(current_account)],
    db: Annotated[Session, Depends(get_session)],
) -> AccountExport:
    response.headers["Cache-Control"] = "no-store"
    from api.commons.account import export_commons
    from api.profile_data import export_profile

    return AccountExport(
        account=account_out(account),
        plans=export_plans(db, account.id),
        profile=export_profile(db, account.id),
        commons=export_commons(db, account.id),
    )


@router.post(
    "/password",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(ip_limit("password", 600))],
)
def change_password(
    body: PasswordChange,
    session: Annotated[SessionData, Depends(require_session)],
    account: Annotated[Account, Depends(current_account)],
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    _confirm_password(store, account, body.current_password)
    account.password_hash = hash_password(body.new_password)
    db.commit()
    destroy_account_sessions(store, account.id, keep=session)


@router.post(
    "/delete",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(ip_limit("delete", 600))],
)
def delete_account(
    body: AccountDelete,
    response: Response,
    account: Annotated[Account, Depends(current_account)],
    db: Annotated[Session, Depends(get_session)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    _refuse_while_restricted(account)
    _confirm_password(store, account, body.password)
    # Deleting and signing up again would wipe the record of a recent upheld removal that a
    # moderator may still act on (for example with a suspension): wait 30 days (P08-12).
    since = dt.datetime.now(dt.UTC).date() - dt.timedelta(days=30)
    if upheld_removals(db, account.id, since) > 0:
        raise HTTPException(
            status_code=409,
            detail="A moderator removed one of your posts in the last 30 days, so this account "
            "cannot be deleted yet.",
        )
    account_id = account.id
    account_data.delete_account(db, account, body.posts)
    db.commit()
    destroy_account_sessions(store, account_id)
    # The dashboard agent's cached greeting restates the student's answers.
    store.delete(welcome_key(account_id))
    clear_session_cookie(response)
