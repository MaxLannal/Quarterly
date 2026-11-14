"""Regex scrub of email addresses and phone numbers, run on every post, comment and title
before anything else sees the text (SPEC A4: "A regex pass strips emails and phone numbers
first"). Deliberately greedy: a false positive costs a few characters, a miss can identify a
student."""

from __future__ import annotations

import re

EMAIL_MARK = "[email removed]"
PHONE_MARK = "[phone removed]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_AT = r"(?:\s*\(at\)\s*|\s*\[at\]\s*|\s*\{at\}\s*|\s+at\s+)"
_DOT = r"(?:\s*\.\s*|\s*\(dot\)\s*|\s*\[dot\]\s*|\s*\{dot\}\s*|\s+dot\s+)"
# "jdoe at uchicago dot edu", "jdoe [at] uchicago [dot] edu", "jdoe(at)uchicago.edu".
_EMAIL_SPELLED = re.compile(
    rf"\b[A-Za-z0-9._%+-]+{_AT}[A-Za-z0-9-]+(?:{_DOT}[A-Za-z0-9-]+)*"
    rf"{_DOT}(?:edu|com|org|net|io|gov|us|me|co)\b",
    re.IGNORECASE,
)
# North American numbers: 773-702-1234, (773) 702 1234, +1 773.702.1234, 7737021234.
_PHONE_NA = re.compile(
    r"(?<![\w+])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"
)
# International: +44 20 7946 0958, +86-10-1234-5678 (a leading + and 8 to 15 digits).
_PHONE_INTL = re.compile(r"\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}(?!\w)")


def _intl(match: re.Match[str]) -> str:
    digits = sum(ch.isdigit() for ch in match[0])
    return PHONE_MARK if 8 <= digits <= 15 else match[0]


def scrub(text: str) -> str:
    """`text` with email addresses and phone numbers replaced by a visible marker."""
    text = _EMAIL.sub(EMAIL_MARK, text)
    text = _EMAIL_SPELLED.sub(EMAIL_MARK, text)
    text = _PHONE_INTL.sub(_intl, text)
    return _PHONE_NA.sub(PHONE_MARK, text)
