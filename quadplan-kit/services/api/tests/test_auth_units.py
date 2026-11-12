"""Auth pieces that need no database: log redaction, the email domain rule, the console email
backend, rate-limit counters and the production settings check."""

import io
import logging
from typing import Any

import fakeredis
import pytest
from api.auth import emails
from api.auth.emails import (
    ConsoleEmailBackend,
    OutgoingEmail,
    SmtpEmailBackend,
    normalize_uchicago_email,
)
from api.auth.hashing import author_ref
from api.auth.passwords import hash_password, verify_password
from api.auth.ratelimit import HOUR, Limit
from api.auth.redaction import RedactingFilter, install_log_redaction, redact
from api.auth.store import Store
from api.config import Settings
from fastapi import HTTPException

EMAIL = "Jane.Doe@uchicago.edu"
IPV4 = "203.0.113.77"
IPV6 = "2001:db8::8a2e:370:7334"


# ------------------------------------------------------------------------------- redaction


@pytest.mark.parametrize(
    "text",
    [
        f"signup for {EMAIL} failed",
        "user=jdoe%40uchicago.edu",
        "Key (email)=(a.b-c_d@uchicago.edu) already exists.",
        "someone@gmail.com, other@cs.uchicago.edu",
        f"client {IPV4}:51234 connected",
        f"from [{IPV6}]:443",
        "peer ::1 and ::ffff:10.0.0.1",
    ],
)
def test_redact_removes_emails_and_ips(text: str) -> None:
    out = redact(text)
    assert "@" not in out and "%40" not in out
    for secret in (EMAIL, "jdoe", "a.b-c_d", "someone", IPV4, IPV6, "::1", "10.0.0.1"):
        assert secret not in out


def test_redact_keeps_ordinary_text() -> None:
    for text in (
        "took 12:34:56 on 2026-11-12",
        "version 1.2.3",
        "GET /auth/session 200",
        "std::map",
    ):
        assert redact(text) == text


def _captured_logger(name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_installed_redaction_scrubs_every_part_of_a_record() -> None:
    """The proof for CLAUDE.md "never log email addresses or IP addresses": message, %-args,
    object args, mapping args and tracebacks are all scrubbed, for any logger."""
    install_log_redaction()
    install_log_redaction()  # idempotent
    logger, stream = _captured_logger("some.third.party")

    class Carrier:
        def __repr__(self) -> str:
            return f"<Carrier {EMAIL}>"

    logger.info("plain %s", EMAIL)
    logger.info(f"interpolated {EMAIL} from {IPV4}")
    logger.info("object %r", Carrier())
    logger.info("mapping %(who)s", {"who": EMAIL})
    logger.info('%s - "%s %s HTTP/%s" %d', f"{IPV4}:5123", "POST", "/auth/email", "1.1", 202)
    try:
        raise ValueError(f"duplicate key (email)=({EMAIL}) from {IPV6}")
    except ValueError:
        logger.exception("boom")
    out = stream.getvalue()
    assert out.count("[email]") >= 5 and "[ip]" in out
    assert "Traceback" in out and "ValueError" in out
    assert '"POST /auth/email HTTP/1.1" 202' in out
    for secret in (EMAIL, EMAIL.lower(), "Jane.Doe", IPV4, IPV6):
        assert secret not in out


def test_redacting_filter_on_a_handler() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "to %s at %s", (EMAIL, IPV4), None)
    assert RedactingFilter().filter(record) is True
    assert record.getMessage() == "to [email] at [ip]"


# ---------------------------------------------------------------------------- email domain


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("student@uchicago.edu", "student@uchicago.edu"),
        ("  Student@UChicago.EDU ", "student@uchicago.edu"),
        ("student@uchicago.edu\n", "student@uchicago.edu"),  # outer whitespace only
        ("first.last-2_x@uchicago.edu", "first.last-2_x@uchicago.edu"),
    ],
)
def test_uchicago_addresses_are_accepted_and_lowercased(raw: str, expected: str) -> None:
    assert normalize_uchicago_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "student@gmail.com",
        "student@cs.uchicago.edu",  # subdomain
        "student@alumni.uchicago.edu",
        "student@uchicago.edu.evil.com",
        "student@evil-uchicago.edu",
        "student@uchicago.edu@evil.com",
        "evil.com/student@uchicago.edu",
        "student@uchicag0.edu",
        "student@uch\u0456cago.edu",  # Cyrillic look-alike of "i"
        "stüdent@uchicago.edu",
        "student+tag@uchicago.edu",
        "a b@uchicago.edu",
        "a..b@uchicago.edu",
        ".a@uchicago.edu",
        "@uchicago.edu",
        "student",
        "",
        "<student@uchicago.edu>",
        "student@uchicago.edu, other@uchicago.edu",
    ],
)
def test_other_addresses_are_rejected(raw: str) -> None:
    assert normalize_uchicago_email(raw) is None


# ----------------------------------------------------------------------------- email backend


def test_console_backend_prints_code_and_pending_id_but_never_the_address(
    capsys: pytest.CaptureFixture[str],
) -> None:
    message = OutgoingEmail(
        to="student@uchicago.edu", kind="signup_code", pending_id="pend-123", code="424242"
    )
    ConsoleEmailBackend().send(message)
    out = capsys.readouterr()
    assert "424242" in out.out and "pend-123" in out.out
    assert "student" not in out.out + out.err and "@" not in out.out + out.err
    assert "student" not in repr(message)


def test_smtp_backend_sends_a_minimal_message_and_logs_failures_without_the_address(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    sent: list[Any] = []

    class FakeSmtp:
        fail = False

        def __init__(self, host: str, port: int, timeout: int) -> None:
            self.tls = False

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def starttls(self, context: Any) -> None:
            assert context.verify_mode.name == "CERT_REQUIRED"
            self.tls = True

        def login(self, user: str, password: str) -> None:
            raise AssertionError("no username configured")

        def send_message(self, mail: Any) -> None:
            assert self.tls
            if FakeSmtp.fail:
                raise emails.smtplib.SMTPRecipientsRefused({mail["To"]: (550, b"no such user")})
            sent.append(mail)

    monkeypatch.setattr(emails.smtplib, "SMTP", FakeSmtp)
    backend = SmtpEmailBackend(Settings(_env_file=None))
    message = OutgoingEmail(
        to="student@uchicago.edu", kind="signup_code", pending_id="pend-123", code="424242"
    )
    backend.send(message)
    (mail,) = sent
    assert mail["To"] == "student@uchicago.edu" and "code" in mail["Subject"]
    assert mail.get_content().strip() == (
        "Your Quarterly verification code is 424242. It expires in 10 minutes."
    )
    FakeSmtp.fail = True
    with caplog.at_level(logging.ERROR):
        backend.send(message)  # does not raise
    assert "SMTPRecipientsRefused" in caplog.text
    assert "student" not in caplog.text and "424242" not in caplog.text


# ------------------------------------------------------------------------------- passwords


def test_passwords_are_hashed_with_argon2id() -> None:
    hashed = hash_password("correct horse battery")
    assert hashed.startswith("$argon2id$")
    assert hashed != hash_password("correct horse battery")  # salted
    assert verify_password(hashed, "correct horse battery")
    assert not verify_password(hashed, "wrong")
    assert not verify_password(None, "correct horse battery")
    assert not verify_password("not-a-hash", "correct horse battery")


# ------------------------------------------------------------------------------ rate limits


def test_limit_counts_in_a_window_and_expires() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = Store(client)
    limit = Limit("t", 3, HOUR)
    for _ in range(3):
        limit.hit(store, "s")
    limit.hit(store, "other")  # separate subject
    with pytest.raises(HTTPException) as err:
        limit.hit(store, "s")
    assert err.value.status_code == 429
    assert 0 < int((err.value.headers or {})["Retry-After"]) <= HOUR
    with pytest.raises(HTTPException):
        limit.check(store, "s")
    assert 0 < client.ttl("rl:t:s") <= HOUR
    client.delete("rl:t:s")  # the window ends
    limit.check(store, "s")


def test_limit_refund_gives_one_event_back_and_never_outlives_the_window() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = Store(client)
    limit = Limit("t", 2, HOUR)
    for _ in range(5):  # good attempts: counted, then given back
        limit.hit(store, "s")
        limit.refund(store, "s")
    limit.hit(store, "s")
    limit.hit(store, "s")
    with pytest.raises(HTTPException):
        limit.hit(store, "s")
    assert 0 < client.ttl("rl:t:s") <= HOUR  # a refund keeps the window's expiry
    client.delete("rl:t:s")  # the window ends before a slow attempt finishes
    limit.refund(store, "s")
    assert client.keys("*") == []  # no negative, never-expiring counter is left behind


# ---------------------------------------------------------------------------------- misc


def test_author_ref_is_per_page_and_stable() -> None:
    import uuid

    a, b = uuid.uuid4(), uuid.uuid4()
    assert author_ref(a, 1) == author_ref(a, 1)
    assert len({author_ref(a, 1), author_ref(a, 2), author_ref(b, 1), author_ref(a, 12)}) == 4
    assert len(author_ref(a, 1)) == 64
    assert str(a) not in author_ref(a, 1)


SAFE = {
    "server_hmac_key": "a" * 40,
    "issuance_hmac_key": "b" * 40,
    "session_secret": "c" * 40,
    "email_backend": "smtp",
}


def test_production_refuses_development_settings() -> None:
    for env in ("development", "test"):
        assert Settings(_env_file=None, environment=env).production_problems() == []
    problems = Settings(
        _env_file=None, environment="production", session_cookie_secure=False
    ).production_problems()
    assert len(problems) == 5
    assert Settings(_env_file=None, environment="production", **SAFE).production_problems() == []


@pytest.mark.parametrize("environment", [None, "", "prod", "staging", "Development", "dev"])
def test_safety_check_fails_closed_unless_the_environment_is_development_or_test(
    environment: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unset or unrecognised ENVIRONMENT is treated as a real deployment."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    if environment is not None:
        monkeypatch.setenv("ENVIRONMENT", environment)

    def problems(**overrides: Any) -> list[str]:
        return Settings(_env_file=None, **{**SAFE, **overrides}).production_problems()

    assert problems() == []
    assert problems(email_backend="console") == [
        "EMAIL_BACKEND=console would print verification codes"
    ]
    assert problems(session_cookie_secure=False) == ["SESSION_COOKIE_SECURE must be true"]
    assert len(Settings(_env_file=None).production_problems()) == 4  # the defaults


def test_app_refuses_to_start_with_unsafe_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from api import main

    unsafe = Settings(_env_file=None, environment="staging", **{**SAFE, "email_backend": "console"})
    monkeypatch.setattr(main, "get_settings", lambda: unsafe)
    with pytest.raises(RuntimeError, match="EMAIL_BACKEND=console"):
        main.create_app()
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, **SAFE))
    main.create_app()
