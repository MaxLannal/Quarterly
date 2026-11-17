"""Rate limits (SPEC "Accounts and anonymity" step 6): fixed-window counters in Redis.

Two kinds of subject: an email/login/account hash, and the client IP. The IP is never stored:
the counter key is a keyed hash of the IP and the current day, lives only in Redis and expires
within 24 hours. Nothing here logs.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from api.auth.hashing import subject_hash
from api.auth.store import Store, get_store
from api.config import get_settings

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR


@dataclass(frozen=True)
class Limit:
    scope: str
    max: int
    window: int  # seconds, at most 24 hours

    def _key(self, subject: str) -> str:
        return f"rl:{self.scope}:{subject}"

    def _reject(self, store: Store, subject: str) -> HTTPException:
        retry = max(store.ttl(self._key(subject)), 1)
        return HTTPException(
            status_code=429,
            detail="Too many attempts. Wait a while and try again.",
            headers={"Retry-After": str(retry)},
        )

    def check(self, store: Store, subject: str) -> None:
        """Raise 429 if the subject has already used up the window (without counting)."""
        if store.count(self._key(subject)) >= self.max:
            raise self._reject(store, subject)

    def record(self, store: Store, subject: str) -> int:
        """Count one event without raising (used for failures after `check`)."""
        return store.incr(self._key(subject), self.window)

    def hit(self, store: Store, subject: str) -> None:
        """Count one event; raise 429 once the subject exceeds the limit."""
        if self.record(store, subject) > self.max:
            raise self._reject(store, subject)

    def refund(self, store: Store, subject: str) -> None:
        """Take back the event a `hit` counted, once the attempt turned out to be good.

        Failure limits count every attempt *before* the secret is checked (`hit`) and refund
        the good ones, so concurrent wrong guesses cannot all slip past a check made earlier.
        """
        store.decr(self._key(subject))


def client_ip(request: Request) -> str:
    """The caller's address, for rate limiting only. Behind our own reverse proxy, set
    TRUSTED_PROXY_HOPS to the number of proxies that append to X-Forwarded-For."""
    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
        forwarded = [p for p in forwarded if p]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def address_bucket(address: str) -> str:
    """What one rate-limit counter covers: an IPv4 address, or an IPv6 /64 (a home or phone
    network gets a whole /64, so moving inside it must not reset the limits)."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


def ip_subject(request: Request) -> str:
    day = dt.datetime.now(dt.UTC).date().isoformat()
    return "ip:" + subject_hash("ip", f"{day}|{address_bucket(client_ip(request))}")


def email_subject(email: str) -> str:
    return "em:" + subject_hash("email", email)


def login_subject(ident: str) -> str:
    return "login:" + subject_hash("login", ident)


def account_subject(account_id: object) -> str:
    return "account:" + subject_hash("account", str(account_id))


def ip_limit(scope: str, per_day: int) -> Callable[..., None]:
    """Dependency: at most `per_day` requests per IP per 24 hours for this endpoint."""
    limit = Limit(f"{scope}:ip", per_day, DAY)

    def dependency(request: Request, store: Annotated[Store, Depends(get_store)]) -> None:
        limit.hit(store, ip_subject(request))

    return dependency


# Per-subject limits. IP limits (on the routes) are loose because a campus network shares
# addresses; the per-email, per-login and per-account limits are the ones that stop guessing.
EMAIL_START_PER_ADDRESS = Limit("email-start", 5, HOUR)
RESET_START_PER_ADDRESS = Limit("reset-start", 5, HOUR)
#: Wrong emailed codes per address, across every code sent to it (sign-up and reset together).
#: Without it, 5 codes an hour x 5 tries each is an unbounded slow search of the 10^6 codes.
CODE_FAILURES_PER_ADDRESS = Limit("code-fail", 10, DAY)
#: Counted per typed login and, when it names an account, per account (username and email
#: share that second budget).
LOGIN_FAILURES = Limit("login-fail", 10, 15 * MINUTE)
PASSWORD_FAILURES = Limit("password-fail", 10, 15 * MINUTE)
