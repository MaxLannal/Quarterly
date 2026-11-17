"""Email addresses and outgoing mail. The address never appears in a log line or in stdout."""

from __future__ import annotations

import logging
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Literal, Protocol

from api.config import Settings, get_settings

logger = logging.getLogger(__name__)

ALLOWED_DOMAIN = "uchicago.edu"
# ASCII only (no Unicode look-alikes), exactly one "@", exactly the University domain (no
# subdomains). "+" is refused so plus-addressing cannot make several accounts for one mailbox.
_ADDRESS = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@uchicago\.edu", re.ASCII)


def normalize_uchicago_email(raw: str) -> str | None:
    """Lowercased address if it is a plain `@uchicago.edu` address, else None."""
    email = raw.strip().lower()
    if not email.isascii() or ".." in email or not _ADDRESS.fullmatch(email):
        return None
    return email


EmailKind = Literal["signup_code", "reset_code", "already_registered"]


@dataclass(frozen=True)
class OutgoingEmail:
    to: str = field(repr=False)  # never in a repr, so never in a log line by accident
    kind: EmailKind
    pending_id: str
    code: str | None = None


class EmailBackend(Protocol):
    def send(self, message: OutgoingEmail) -> None: ...


class ConsoleEmailBackend:
    """Development: prints the code and pending id to stdout. Never prints the address."""

    def send(self, message: OutgoingEmail) -> None:
        print(
            f"[email:console] kind={message.kind} pending_id={message.pending_id} "
            f"code={message.code or '-'}",
            file=sys.stdout,
            flush=True,
        )


SUBJECTS: dict[EmailKind, str] = {
    "signup_code": "Your Quarterly verification code",
    "reset_code": "Your Quarterly password reset code",
    "already_registered": "You already have a Quarterly account",
}


def render_body(message: OutgoingEmail) -> str:
    """Minimal text (SPEC: "a minimal message")."""
    if message.kind == "signup_code":
        return f"Your Quarterly verification code is {message.code}. It expires in 10 minutes."
    if message.kind == "reset_code":
        return (
            f"Your Quarterly password reset code is {message.code}. It expires in 10 minutes. "
            "If you did not ask for it, ignore this message."
        )
    return (
        "Someone tried to create a Quarterly account with this address, but it already has one. "
        "Log in, or use 'Forgot password' to reset your password. If this was not you, ignore "
        "this message."
    )


class SmtpEmailBackend:
    """Any transactional provider's SMTP endpoint (STARTTLS, certificate verified)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: OutgoingEmail) -> None:
        s = self._settings
        mail = EmailMessage()
        mail["From"] = s.email_from
        mail["To"] = message.to
        mail["Subject"] = SUBJECTS[message.kind]
        mail.set_content(render_body(message))
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
                smtp.send_message(mail)
        except (smtplib.SMTPException, OSError) as exc:
            # The exception text can quote the recipient; log its type only.
            logger.error("email send failed: kind=%s error=%s", message.kind, type(exc).__name__)


def get_email_backend() -> EmailBackend:
    """FastAPI dependency."""
    settings = get_settings()
    if settings.email_backend == "smtp":
        return SmtpEmailBackend(settings)
    return ConsoleEmailBackend()
