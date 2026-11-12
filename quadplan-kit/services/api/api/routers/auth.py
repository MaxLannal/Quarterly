from fastapi import APIRouter, Response

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
from api.schemas.common import NOT_IMPLEMENTED, not_implemented

router = APIRouter(prefix="/auth", tags=["auth"], responses=NOT_IMPLEMENTED)


@router.post("/email", response_model=EmailStarted, status_code=202)
def start_email(body: EmailStart) -> EmailStarted:
    raise not_implemented("04")


@router.post("/verify-code", response_model=RegistrationTicket)
def verify_code(body: VerifyCode) -> RegistrationTicket:
    raise not_implemented("04")


@router.post("/register", response_model=SessionOut, status_code=201)
def register(body: Register) -> SessionOut:
    raise not_implemented("04")


@router.post("/login", response_model=SessionOut)
def login(body: Login) -> SessionOut:
    raise not_implemented("04")


@router.post("/logout", status_code=204, response_class=Response)
def logout() -> None:
    raise not_implemented("04")


@router.get("/session", response_model=SessionOut)
def current_session() -> SessionOut:
    raise not_implemented("04")


@router.post("/password-reset/start", response_model=EmailStarted, status_code=202)
def start_password_reset(body: PasswordResetStart) -> EmailStarted:
    raise not_implemented("04")


@router.post("/password-reset/finish", status_code=204, response_class=Response)
def finish_password_reset(body: PasswordResetFinish) -> None:
    raise not_implemented("04")
