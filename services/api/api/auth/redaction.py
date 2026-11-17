"""Log redaction: nothing shaped like an email address or an IP address reaches a log line.

`install_log_redaction()` wraps the process-wide log record factory, so every record from every
logger (ours, uvicorn's, SQLAlchemy's) is scrubbed before any handler or formatter sees it.
`RedactingFilter` is the same scrubber as a `logging.Filter` for handlers configured elsewhere.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import traceback
from typing import Any

EMAIL_MARK = "[email]"
IP_MARK = "[ip]"

# Deliberately broad: `local@host` with or without a dot, and the URL-encoded `%40` form.
_EMAIL = re.compile(r"[\w.+\-]+(?:@|%40)[\w\-]+(?:\.[\w\-]+)*", re.IGNORECASE)
_IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
# Candidates only; `_ip_or_same` keeps what `ipaddress` does not accept (e.g. "12:34:56").
_IPV6 = re.compile(
    r"(?<![\w:.])(?:[0-9A-Fa-f]{0,4}:){2,7}(?:(?:\d{1,3}\.){3}\d{1,3}|[0-9A-Fa-f]{1,4})?"
)


def _ip_or_same(match: re.Match[str]) -> str:
    text = match.group(0)
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return text
    return IP_MARK


def redact(text: str) -> str:
    """Replace email-shaped and IP-shaped substrings."""
    text = _EMAIL.sub(EMAIL_MARK, text)
    text = _IPV6.sub(_ip_or_same, text)
    return _IPV4.sub(_ip_or_same, text)


def _redact_arg(arg: Any) -> Any:
    if isinstance(arg, str):
        return redact(arg)
    if arg is None or isinstance(arg, bool | int | float):
        return arg
    try:
        shown = (str(arg), repr(arg))
    except Exception:
        return "[unprintable]"
    if all(redact(s) == s for s in shown):
        return arg
    return redact(shown[0])


def redact_record(record: logging.LogRecord) -> None:
    record.msg = _redact_arg(record.msg)
    if isinstance(record.args, tuple):
        record.args = tuple(_redact_arg(a) for a in record.args)
    elif isinstance(record.args, dict):
        record.args = {k: _redact_arg(v) for k, v in record.args.items()}
    if record.exc_info and isinstance(record.exc_info, tuple) and record.exc_info[0] is not None:
        # Exception messages can quote user input (e.g. a unique-violation detail). Format the
        # traceback now, scrubbed, and drop the live exception so no handler can re-format it.
        record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)).rstrip())
        record.exc_info = None
    elif record.exc_text:
        record.exc_text = redact(record.exc_text)
    if record.stack_info:
        record.stack_info = redact(record.stack_info)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        redact_record(record)
        return True


_MARKER = "_quarterly_redacting"


def install_log_redaction() -> None:
    """Idempotent. Call once at application start-up (api.main.create_app does)."""
    current = logging.getLogRecordFactory()
    if getattr(current, _MARKER, False):
        return

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = current(*args, **kwargs)
        redact_record(record)
        return record

    setattr(factory, _MARKER, True)
    logging.setLogRecordFactory(factory)
