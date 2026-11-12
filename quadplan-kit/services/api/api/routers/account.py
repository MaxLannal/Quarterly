"""`/account`: export, change password, delete (SPEC "Account deletion")."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from api.auth import account_data
from api.auth.account_data import account_out, export_plans
from api.auth.hashing import subject_hash
from api.auth.passwords import hash_password, verify_password
from api.auth.ratelimit import PASSWORD_FAILURES, ip_limit
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
from api.schemas.auth import AccountDelete, AccountExport, PasswordChange
from api.schemas.common import NOT_IMPLEMENTED

router = APIRouter(prefix="/account", tags=["account"], responses=NOT_IMPLEMENTED)


def _confirm_password(store: Store, account: Account, password: str) -> None:
    """Re-authentication for sensitive actions, with its own per-account failure limit."""
    subject = "account:" + subject_hash("account", str(account.id))
    PASSWORD_FAILURES.check(store, subject)
    # The frozen schemas put no length cap on these fields; do not hash huge inputs.
    if len(password) > 256 or not verify_password(account.password_hash, password):
        PASSWORD_FAILURES.record(store, subject)
        raise HTTPException(status_code=403, detail="That password is wrong.")


@router.get(
    "/export", response_model=AccountExport, dependencies=[Depends(ip_limit("export", 600))]
)
def export_account(
    response: Response,
    account: Annotated[Account, Depends(current_account)],
    db: Annotated[Session, Depends(get_session)],
) -> AccountExport:
    response.headers["Cache-Control"] = "no-store"
    return AccountExport(account=account_out(account), plans=export_plans(db, account.id))


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
    _confirm_password(store, account, body.password)
    account_id = account.id
    account_data.delete_account(db, account, body.posts)
    db.commit()
    destroy_account_sessions(store, account_id)
    clear_session_cookie(response)
