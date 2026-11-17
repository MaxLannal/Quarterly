"""argon2id password hashing (argon2-cffi defaults: RFC 9106 low-memory profile)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from fastapi import HTTPException

_hasher = PasswordHasher(type=Type.ID)

#: At most this many argon2id hashes at once per API process. Each uses 64 MiB, and a burst
#: of logins (40 requests at once per process, 4 processes) could otherwise take ~10 GiB and
#: run the server out of memory (final security review E). A request that cannot start one
#: within WAIT_S gets a 503.
MAX_CONCURRENT = 4
WAIT_S = 5.0
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)


@contextmanager
def _slot() -> Iterator[None]:
    if not _slots.acquire(timeout=WAIT_S):
        raise HTTPException(
            status_code=503,
            detail="The server is busy. Try again in a moment.",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        _slots.release()


def hash_password(password: str) -> str:
    with _slot():
        return _hasher.hash(password)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("no-such-account-placeholder")


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Same work whether or not the account exists (no timing oracle for usernames)."""
    with _slot():
        try:
            _hasher.verify(stored_hash or _dummy_hash(), password)
        except (VerificationError, InvalidHashError):
            return False
    return stored_hash is not None


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
