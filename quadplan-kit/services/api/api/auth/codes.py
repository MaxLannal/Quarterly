"""Emailed 6-digit codes and registration tickets (SPEC protocol steps 1, 2 and 5).

A pending verification lives in Redis for 10 minutes under an opaque `pending_id`; the code is
stored as a keyed hash. A "dead" pending record (no email, a hash no code can match) is created
when the server must not reveal that it sent nothing, so every `pending_id` behaves the same
for someone who cannot read the mailbox.
"""

from __future__ import annotations

import hmac
import json
import secrets
from typing import Literal

from fastapi import HTTPException

from api.auth.hashing import secret_hash, token_key
from api.auth.store import Store

PENDING_TTL = 600
TICKET_TTL = 600
MAX_ATTEMPTS = 5

Kind = Literal["signup", "reset"]

INVALID_CODE = "That code is wrong or has expired."
TOO_MANY = "Too many wrong codes. Request a new code."


def _pending_key(pending_id: str) -> str:
    return f"auth:pending:{token_key(pending_id)}"


def _attempts_key(pending_id: str) -> str:
    return f"auth:pending-attempts:{token_key(pending_id)}"


def _ticket_key(ticket: str) -> str:
    return f"auth:ticket:{token_key(ticket)}"


def _code_hash(pending_id: str, code: str) -> str:
    return secret_hash("code", pending_id, code)


def create_pending(store: Store, kind: Kind, email: str | None) -> tuple[str, str | None]:
    """Returns (pending_id, code). `email=None` makes a dead record and returns no code."""
    pending_id = secrets.token_urlsafe(24)
    code: str | None
    if email is None:
        code, hashed = None, _code_hash(pending_id, secrets.token_hex(16))
    else:
        code = f"{secrets.randbelow(10**6):06d}"
        hashed = _code_hash(pending_id, code)
    record = json.dumps({"kind": kind, "email": email, "hash": hashed})
    store.put(_pending_key(pending_id), record, PENDING_TTL)
    return pending_id, code


def redeem_pending(store: Store, kind: Kind, pending_id: str, code: str) -> str:
    """The verified email. One use; at most MAX_ATTEMPTS tries, then the record is destroyed."""
    attempts = store.incr(_attempts_key(pending_id), PENDING_TTL)
    if attempts > MAX_ATTEMPTS:
        store.delete(_pending_key(pending_id))
        raise HTTPException(status_code=429, detail=TOO_MANY)
    raw = store.get(_pending_key(pending_id))
    invalid = HTTPException(status_code=400, detail=INVALID_CODE)
    if raw is None:
        raise invalid
    record = json.loads(raw)
    matches = hmac.compare_digest(str(record["hash"]), _code_hash(pending_id, code))
    if record["kind"] != kind or not matches or record["email"] is None:
        raise invalid
    if store.getdel(_pending_key(pending_id)) is None:  # a concurrent request used it first
        raise invalid
    store.delete(_attempts_key(pending_id))
    return str(record["email"])


def create_ticket(store: Store, email: str) -> str:
    ticket = secrets.token_urlsafe(32)
    store.put(_ticket_key(ticket), email, TICKET_TTL)
    return ticket


def peek_ticket(store: Store, ticket: str) -> str | None:
    return store.get(_ticket_key(ticket))


def delete_ticket(store: Store, ticket: str) -> None:
    store.delete(_ticket_key(ticket))
