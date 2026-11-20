"""Identity in the Commons (docs/BEST-OF-UCHICAGO-PLAN.md): every author, voter and reporter of a
thread is stored as `commons_ref(account_id, thread_id)`, never as the account id.

The HMAC message is domain-separated ("commons|..."), so a Commons ref never equals the forum's
`author_ref(account_id, page_id)` even when a thread id equals a forum page id: knowing one says
nothing about the other. Account export and deletion recompute the refs for every thread.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from api.config import get_settings

_DOMAIN = b"commons|"


def commons_ref(account_id: uuid.UUID, thread_id: int) -> str:
    """HMAC-SHA256(server_hmac_key, "commons|" || account_id || "|" || thread_id), hex."""
    key = get_settings().server_hmac_key.get_secret_value().encode()
    message = _DOMAIN + account_id.bytes + b"|" + str(thread_id).encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def presence_key(ref: str) -> str:
    """A short, non-reversible id for the typing key (the ref itself never reaches Redis)."""
    return hashlib.sha256(b"typing|" + ref.encode()).hexdigest()[:16]
