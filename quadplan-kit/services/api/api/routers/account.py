from fastapi import APIRouter, Response

from api.schemas.auth import AccountDelete, AccountExport, PasswordChange
from api.schemas.common import NOT_IMPLEMENTED, not_implemented

router = APIRouter(prefix="/account", tags=["account"], responses=NOT_IMPLEMENTED)


@router.get("/export", response_model=AccountExport)
def export_account() -> AccountExport:
    raise not_implemented("04")


@router.post("/password", status_code=204, response_class=Response)
def change_password(body: PasswordChange) -> None:
    raise not_implemented("04")


@router.post("/delete", status_code=204, response_class=Response)
def delete_account(body: AccountDelete) -> None:
    raise not_implemented("04")
