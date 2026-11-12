"""argon2id password hashing (argon2-cffi defaults: RFC 9106 low-memory profile)."""

from __future__ import annotations

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("no-such-account-placeholder")


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Same work whether or not the account exists (no timing oracle for usernames)."""
    try:
        _hasher.verify(stored_hash or _dummy_hash(), password)
    except (VerificationError, InvalidHashError):
        return False
    return stored_hash is not None


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
