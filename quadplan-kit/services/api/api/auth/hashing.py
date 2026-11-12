"""Keyed hashes: identifiers that must not be stored or compared in the clear."""

from __future__ import annotations

import hashlib
import hmac
import uuid

from api.config import get_settings


def _hmac(key: bytes, *parts: str) -> str:
    return hmac.new(key, "\x1f".join(parts).encode(), hashlib.sha256).hexdigest()


def subject_hash(purpose: str, value: str) -> str:
    """Rate-limit subject (an email address, a login name, an IP): never stored in the clear."""
    return _hmac(get_settings().issuance_hmac_key.get_secret_value().encode(), purpose, value)


def secret_hash(purpose: str, *parts: str) -> str:
    """Hash of a short secret (a 6-digit code): keyed, so the Redis value alone cannot be
    brute-forced."""
    return _hmac(get_settings().session_secret.get_secret_value().encode(), purpose, *parts)


def token_key(token: str) -> str:
    """Redis key part for a high-entropy bearer token (session id, pending id, ticket), so a
    dump of Redis does not contain usable tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def author_ref(account_id: uuid.UUID, page_id: int) -> str:
    """SPEC: `author_ref = HMAC(server_key, account_id || page_id)`, the per-page forum identity
    (`post.author_ref`, `comment.author_ref`, `vote.voter_ref`, `pseudonym.author_ref`,
    `report.reporter_ref`). `page_id` is `course_instructor.id`. The forum must use this
    function: account deletion recomputes it to find an account's posts."""
    key = get_settings().server_hmac_key.get_secret_value().encode()
    message = account_id.bytes + b"|" + str(page_id).encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()
