"""Accounts per decision 5 (SPEC "Accounts and anonymity"): verified @uchicago.edu email +
argon2id password; Redis sessions with a CSRF token."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.plans import PlanOut

USERNAME = r"^[A-Za-z0-9_-]{3,32}$"


class EmailStart(BaseModel):
    email: str = Field(max_length=254)


class EmailStarted(BaseModel):
    pending_id: str


class VerifyCode(BaseModel):
    pending_id: str
    code: str = Field(pattern=r"^\d{6}$")


class RegistrationTicket(BaseModel):
    ticket: str


class Register(BaseModel):
    ticket: str
    username: str = Field(pattern=USERNAME)
    password: str = Field(min_length=12, max_length=256)


class Login(BaseModel):
    #: Username or email.
    login: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AccountOut(BaseModel):
    id: uuid.UUID
    username: str
    role: Literal["user", "curator", "admin"]
    created_day: dt.date


class SessionOut(BaseModel):
    account: AccountOut
    #: Send back as the X-CSRF-Token header on every state-changing request.
    csrf_token: str


class PasswordResetStart(BaseModel):
    email: str = Field(max_length=254)


class PasswordResetFinish(BaseModel):
    pending_id: str
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=12, max_length=256)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=256)


class AccountExport(BaseModel):
    account: AccountOut
    plans: list[PlanOut] = []


class AccountDelete(BaseModel):
    password: str
    posts: Literal["delete", "keep"]
