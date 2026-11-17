"""SPEC "Accounts and anonymity" protocol steps 1-6 through the HTTP API."""

import datetime as dt
import logging
from collections.abc import Iterator

import pytest
from api.auth import codes
from api.auth.sessions import CSRF_EXEMPT_PATHS
from api.config import get_settings
from auth_test_support import PASSWORD, Env, auth_env, csrf, migrated_database
from sqlalchemy import inspect, text

pytestmark = pytest.mark.db

EMAIL = "quiet-heron@uchicago.edu"
COOKIE = "__Host-qp_session"


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    with auth_env(db_url, monkeypatch) as e:
        yield e


def start(env: Env, email: str = EMAIL) -> str:
    resp = env.client.post("/auth/email", json={"email": email})
    assert resp.status_code == 202, resp.text
    return str(resp.json()["pending_id"])


# ------------------------------------------------------------------------ step 1: the email


@pytest.mark.parametrize(
    "email",
    ["student@gmail.com", "student@cs.uchicago.edu", "student@uchicago.edu.evil.com", "nope"],
)
def test_only_uchicago_addresses_may_start(env: Env, email: str) -> None:
    resp = env.client.post("/auth/email", json={"email": email})
    assert resp.status_code == 400
    assert "uchicago.edu" in resp.json()["detail"]
    assert env.outbox.sent == [] and env.redis.keys("auth:*") == []


def test_email_step_stores_a_hashed_code_for_ten_minutes(env: Env) -> None:
    pending_id = start(env, "Quiet-Heron@UChicago.edu")
    message = env.outbox.last()
    assert message.to == EMAIL and message.kind == "signup_code"
    assert message.code is not None and len(message.code) == 6 and message.code.isdigit()
    assert message.pending_id == pending_id
    (key,) = env.redis.keys("auth:pending:*")
    assert pending_id not in key  # opaque id is not stored in the clear
    assert message.code not in env.redis.get(key)
    assert 590 < env.redis.ttl(key) <= 600


# ------------------------------------------------------------------------- step 2: the code


def test_code_gives_a_one_time_ticket_bound_to_the_email(env: Env) -> None:
    pending_id = start(env)
    body = {"pending_id": pending_id, "code": env.outbox.last().code}
    resp = env.client.post("/auth/verify-code", json=body)
    assert resp.status_code == 200
    (key,) = env.redis.keys("auth:ticket:*")
    assert env.redis.get(key) == EMAIL and 590 < env.redis.ttl(key) <= 600
    assert env.redis.keys("auth:pending:*") == []
    # The code cannot be used twice.
    assert env.client.post("/auth/verify-code", json=body).status_code == 400


def test_expired_code_is_rejected(env: Env) -> None:
    pending_id = start(env)
    env.redis.delete(*env.redis.keys("auth:pending:*"))  # what Redis does after 10 minutes
    resp = env.client.post(
        "/auth/verify-code", json={"pending_id": pending_id, "code": env.outbox.last().code}
    )
    assert resp.status_code == 400 and resp.json()["detail"] == codes.INVALID_CODE


def test_wrong_code_attempts_are_limited(env: Env) -> None:
    pending_id = start(env)
    good = env.outbox.last().code
    assert good is not None
    bad = "000000" if good != "000000" else "111111"
    for _ in range(codes.MAX_ATTEMPTS):
        resp = env.client.post("/auth/verify-code", json={"pending_id": pending_id, "code": bad})
        assert resp.status_code == 400
    resp = env.client.post("/auth/verify-code", json={"pending_id": pending_id, "code": bad})
    assert resp.status_code == 429
    # The record is gone: even the right code no longer works.
    resp = env.client.post("/auth/verify-code", json={"pending_id": pending_id, "code": good})
    assert resp.status_code in (400, 429)
    assert env.redis.keys("auth:pending:*") == [] and env.redis.keys("auth:ticket:*") == []


def test_malformed_code_is_a_validation_error(env: Env) -> None:
    resp = env.client.post("/auth/verify-code", json={"pending_id": start(env), "code": "12345a"})
    assert resp.status_code == 422


# --------------------------------------------------------------------- step 3: registration


def test_registration_creates_the_account_and_starts_a_session(env: Env) -> None:
    ticket = env.verified_ticket("Quiet-Heron@UChicago.EDU")
    resp = env.client.post(
        "/auth/register", json={"ticket": ticket, "username": "Quiet-Heron", "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["account"]["username"] == "Quiet-Heron" and body["account"]["role"] == "user"
    assert set(body["account"]) == {"id", "username", "role", "created_day"}  # no email
    assert body["csrf_token"]
    assert env.redis.keys("auth:ticket:*") == []  # ticket deleted

    with env.db() as db:
        row = db.execute(text("SELECT * FROM account")).mappings().one()
    assert row["email"] == EMAIL
    assert row["email_verified_day"] == dt.datetime.now(dt.UTC).date()
    assert isinstance(row["email_verified_day"], dt.date)
    assert row["password_hash"].startswith("$argon2id$") and PASSWORD not in row["password_hash"]

    session = env.client.get("/auth/session")
    assert session.status_code == 200 and session.json() == body
    # The ticket is single-use.
    again = env.browser().post(
        "/auth/register", json={"ticket": ticket, "username": "other", "password": PASSWORD}
    )
    assert again.status_code == 400


def test_session_cookie_flags(env: Env) -> None:
    ticket = env.verified_ticket(EMAIL)
    resp = env.client.post(
        "/auth/register", json={"ticket": ticket, "username": "quiet-heron", "password": PASSWORD}
    )
    cookie = resp.headers["set-cookie"]
    name, _, rest = cookie.partition("=")
    attrs = {a.strip().lower() for a in rest.split(";")[1:]}
    assert name == COOKIE
    assert {"httponly", "secure", "samesite=lax", "path=/"} <= attrs
    assert not any(a.startswith("domain") for a in attrs)
    assert resp.headers["cache-control"] == "no-store"
    # The cookie value is not what Redis stores, and the session has no timestamp.
    sid = rest.split(";")[0]
    assert sid not in env.redis_dump()


def test_cookie_is_not_secure_only_when_configured_for_local_http(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "session_cookie_secure", False)
    ticket = env.verified_ticket(EMAIL)
    resp = env.client.post(
        "/auth/register", json={"ticket": ticket, "username": "quiet-heron", "password": PASSWORD}
    )
    cookie = resp.headers["set-cookie"].lower()
    assert cookie.startswith("qp_session=") and "secure" not in cookie and "httponly" in cookie


def test_one_account_per_email(env: Env) -> None:
    # Two verifications of the same address in flight: only one can register.
    first = env.verified_ticket(EMAIL)
    second = env.verified_ticket(EMAIL)
    a = env.browser().post(
        "/auth/register", json={"ticket": first, "username": "first", "password": PASSWORD}
    )
    b = env.browser().post(
        "/auth/register", json={"ticket": second, "username": "second", "password": PASSWORD}
    )
    assert (a.status_code, b.status_code) == (201, 409)
    with env.db() as db:
        assert db.execute(text("SELECT count(*) FROM account")).scalar_one() == 1


def test_existing_email_is_refused_without_telling_the_caller(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    fresh = env.browser()
    known = fresh.post("/auth/email", json={"email": "QUIET-heron@uchicago.edu"})
    unknown = fresh.post("/auth/email", json={"email": "someone-else@uchicago.edu"})
    # Same status and same shape for both.
    assert known.status_code == unknown.status_code == 202
    assert set(known.json()) == set(unknown.json()) == {"pending_id"}
    assert len(known.json()["pending_id"]) == len(unknown.json()["pending_id"])
    notice = env.outbox.sent[-2]
    assert notice.kind == "already_registered" and notice.code is None
    # No code can redeem the pending id, and it fails exactly like a wrong code.
    for _ in range(codes.MAX_ATTEMPTS):
        resp = fresh.post(
            "/auth/verify-code", json={"pending_id": known.json()["pending_id"], "code": "123456"}
        )
        assert resp.status_code == 400 and resp.json()["detail"] == codes.INVALID_CODE
    resp = fresh.post(
        "/auth/verify-code", json={"pending_id": known.json()["pending_id"], "code": "123456"}
    )
    assert resp.status_code == 429
    assert env.redis.keys("auth:ticket:*") == []


def test_usernames_are_unique_ignoring_case(env: Env) -> None:
    env.signup("Quiet-Heron", EMAIL)
    ticket = env.verified_ticket("second@uchicago.edu", env.browser())
    other = env.browser()
    resp = other.post(
        "/auth/register", json={"ticket": ticket, "username": "quiet-HERON", "password": PASSWORD}
    )
    assert resp.status_code == 409 and "username" in resp.json()["detail"]
    # The ticket survives a username clash.
    resp = other.post(
        "/auth/register", json={"ticket": ticket, "username": "loud-heron", "password": PASSWORD}
    )
    assert resp.status_code == 201


@pytest.mark.parametrize(
    "fields",
    [{"username": "ab"}, {"username": "has space"}, {"username": "a@b.c"}, {"password": "short"}],
)
def test_register_validates_username_and_password(env: Env, fields: dict[str, str]) -> None:
    body = {"ticket": "t", "username": "quiet-heron", "password": PASSWORD, **fields}
    assert env.client.post("/auth/register", json=body).status_code == 422


def test_register_needs_a_valid_ticket(env: Env) -> None:
    resp = env.client.post(
        "/auth/register",
        json={"ticket": "made-up", "username": "quiet-heron", "password": PASSWORD},
    )
    assert resp.status_code == 400
    assert "set-cookie" not in resp.headers


# --------------------------------------------------------------------- step 4: login, sessions


def test_login_by_username_or_email(env: Env) -> None:
    created = env.signup("Quiet-Heron", EMAIL)
    for login in ("Quiet-Heron", "quiet-heron", EMAIL, "QUIET-HERON@UChicago.edu"):
        browser = env.browser()
        resp = browser.post("/auth/login", json={"login": login, "password": PASSWORD})
        assert resp.status_code == 200, login
        assert resp.json()["account"] == created["account"]
        assert browser.get("/auth/session").json()["csrf_token"] == resp.json()["csrf_token"]


def test_bad_logins_look_the_same(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    browser = env.browser()
    wrong = browser.post("/auth/login", json={"login": "quiet-heron", "password": "wrong-password"})
    nobody = browser.post("/auth/login", json={"login": "no-such-user", "password": PASSWORD})
    no_mail = browser.post("/auth/login", json={"login": "x@uchicago.edu", "password": PASSWORD})
    assert wrong.status_code == nobody.status_code == no_mail.status_code == 401
    assert wrong.json() == nobody.json() == no_mail.json()
    assert "set-cookie" not in wrong.headers
    assert browser.get("/auth/session").status_code == 401


def test_session_id_rotates_on_login_and_is_never_taken_from_the_request(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    first_sid = env.client.cookies.get(COOKIE)
    # Logging in again in the same browser issues a new id and ends the old session.
    resp = env.client.post("/auth/login", json={"login": "quiet-heron", "password": PASSWORD})
    second_sid = env.client.cookies.get(COOKIE)
    assert resp.status_code == 200 and first_sid and second_sid and first_sid != second_sid
    stale = env.browser()
    stale.cookies.set(COOKIE, first_sid, domain="testserver.local")
    assert stale.get("/auth/session").status_code == 401

    # Fixation: an attacker-chosen cookie value is not adopted at login.
    victim = env.browser()
    victim.cookies.set(COOKIE, "attacker-chosen-session-id", domain="testserver.local")
    assert (
        victim.post("/auth/login", json={"login": "quiet-heron", "password": PASSWORD}).status_code
        == 200
    )
    assert victim.cookies.get(COOKIE, domain="testserver.local") not in (
        None,
        "attacker-chosen-session-id",
    )
    attacker = env.browser()
    attacker.cookies.set(COOKIE, "attacker-chosen-session-id", domain="testserver.local")
    assert attacker.get("/auth/session").status_code == 401


def test_logout_invalidates_the_session(env: Env) -> None:
    session = env.signup("quiet-heron", EMAIL)
    sid = env.client.cookies.get(COOKIE)
    assert sid
    resp = env.client.post("/auth/logout", headers=csrf(session))
    assert resp.status_code == 204
    assert "max-age=0" in resp.headers["set-cookie"].lower()
    assert env.client.get("/auth/session").status_code == 401
    replay = env.browser()
    replay.cookies.set(COOKIE, sid, domain="testserver.local")
    assert replay.get("/auth/session").status_code == 401
    assert env.redis.keys("sess:*") == []
    # Logging out twice is harmless.
    assert env.browser().post("/auth/logout").status_code == 204


def test_session_requires_login(env: Env) -> None:
    assert env.client.get("/auth/session").status_code == 401


def test_csrf_token_is_required_on_cookie_authenticated_writes(env: Env) -> None:
    session = env.signup("quiet-heron", EMAIL)
    # Missing and wrong tokens are refused before the endpoint runs, on every router.
    for path, body in (
        ("/auth/logout", None),
        ("/account/password", {"current_password": PASSWORD, "new_password": PASSWORD + "2"}),
        ("/account/delete", {"password": PASSWORD, "posts": "keep"}),
        ("/plans", {"name": "p", "state": {"catalog_year": "2026-27", "entry_term": "2026-AU"}}),
        ("/forum/votes", {"target_type": "post", "target_id": 1, "value": 1}),
    ):
        assert env.client.post(path, json=body).status_code == 403, path
        wrong = env.client.post(path, json=body, headers={"X-CSRF-Token": "nope"})
        assert wrong.status_code == 403, path
    assert env.client.delete("/plans/00000000-0000-0000-0000-000000000001").status_code == 403
    # Nothing happened.
    assert env.client.get("/auth/session").status_code == 200
    # With the token the request reaches the endpoint (no such post: 404).
    ok = env.client.post(
        "/forum/votes",
        json={"target_type": "post", "target_id": 1, "value": 1},
        headers=csrf(session),
    )
    assert ok.status_code == 404
    # Another session's token does not work.
    other = env.signup("other-user", "other@uchicago.edu", client=env.browser())
    assert env.client.post("/auth/logout", headers=csrf(other)).status_code == 403
    # Reads need no token; requests without a session cookie are not affected.
    assert env.client.get("/account/export").status_code == 200
    assert (
        env.browser()
        .post("/forum/votes", json={"target_type": "post", "target_id": 1, "value": 1})
        .status_code
        == 401  # not the CSRF guard's 403: no session, so the endpoint asks for a login
    )


def test_csrf_exemptions_are_only_the_sessionless_endpoints() -> None:
    assert CSRF_EXEMPT_PATHS == {  # noqa: SIM300
        "/auth/email",
        "/auth/verify-code",
        "/auth/register",
        "/auth/login",
        "/auth/password-reset/start",
        "/auth/password-reset/finish",
        "/verify",
    }


# ------------------------------------------------------------------- step 5: password reset


def test_password_reset_flow(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    phone = env.browser()
    assert phone.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200

    fresh = env.browser()
    started = fresh.post("/auth/password-reset/start", json={"email": "Quiet-Heron@uchicago.edu"})
    assert started.status_code == 202
    message = env.outbox.last()
    assert message.kind == "reset_code" and message.to == EMAIL and message.code
    pending_id = started.json()["pending_id"]
    (key,) = env.redis.keys("auth:pending:*")
    assert 590 < env.redis.ttl(key) <= 600

    new_password = "a brand new password"
    # A reset code is not a sign-up code.
    assert (
        fresh.post(
            "/auth/verify-code", json={"pending_id": pending_id, "code": message.code}
        ).status_code
        == 400
    )
    short = fresh.post(
        "/auth/password-reset/finish",
        json={"pending_id": pending_id, "code": message.code, "new_password": "short"},
    )
    assert short.status_code == 422
    done = fresh.post(
        "/auth/password-reset/finish",
        json={"pending_id": pending_id, "code": message.code, "new_password": new_password},
    )
    assert done.status_code == 204, done.text
    # Every earlier session is over; the old password is dead; the new one works.
    assert env.client.get("/auth/session").status_code == 401
    assert phone.get("/auth/session").status_code == 401
    assert fresh.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 401
    assert (
        fresh.post("/auth/login", json={"login": EMAIL, "password": new_password}).status_code
        == 200
    )
    with env.db() as db:
        assert (
            db.execute(text("SELECT password_hash FROM account"))
            .scalar_one()
            .startswith("$argon2id$")
        )
    # The code was single-use.
    again = env.browser().post(
        "/auth/password-reset/finish",
        json={"pending_id": pending_id, "code": message.code, "new_password": new_password},
    )
    assert again.status_code == 400


def test_password_reset_never_reveals_whether_an_account_exists(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    fresh = env.browser()
    sent_before = len(env.outbox.sent)
    known = fresh.post("/auth/password-reset/start", json={"email": EMAIL})
    unknown = fresh.post("/auth/password-reset/start", json={"email": "nobody@uchicago.edu"})
    outside = fresh.post("/auth/password-reset/start", json={"email": "nobody@gmail.com"})
    assert known.status_code == unknown.status_code == outside.status_code == 202
    assert set(known.json()) == set(unknown.json()) == set(outside.json()) == {"pending_id"}
    assert len(env.outbox.sent) == sent_before + 1  # only the real account got mail
    assert len(env.redis.keys("auth:pending:*")) == 3  # all three look alive
    for resp in (unknown, outside):
        finish = fresh.post(
            "/auth/password-reset/finish",
            json={
                "pending_id": resp.json()["pending_id"],
                "code": "123456",
                "new_password": "a brand new password",
            },
        )
        assert finish.status_code == 400 and finish.json()["detail"] == codes.INVALID_CODE


def test_reset_code_attempts_are_limited(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    fresh = env.browser()
    pending_id = fresh.post("/auth/password-reset/start", json={"email": EMAIL}).json()[
        "pending_id"
    ]
    good = env.outbox.last().code
    bad = "000000" if good != "000000" else "111111"
    body = {"pending_id": pending_id, "code": bad, "new_password": "a brand new password"}
    for _ in range(codes.MAX_ATTEMPTS):
        assert fresh.post("/auth/password-reset/finish", json=body).status_code == 400
    assert fresh.post("/auth/password-reset/finish", json=body).status_code == 429
    assert fresh.post("/auth/password-reset/finish", json={**body, "code": good}).status_code in (
        400,
        429,
    )
    assert fresh.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200


# --------------------------------------------------------------------- step 6: rate limits


def test_email_step_is_limited_per_address(env: Env) -> None:
    for _ in range(5):
        start(env)
    resp = env.client.post("/auth/email", json={"email": "QUIET-HERON@uchicago.edu"})
    assert resp.status_code == 429 and int(resp.headers["retry-after"]) > 0
    assert len(env.outbox.sent) == 5
    start(env, "someone-else@uchicago.edu")  # other addresses are unaffected


def test_reset_start_is_limited_per_address(env: Env) -> None:
    for _ in range(5):
        assert (
            env.client.post("/auth/password-reset/start", json={"email": EMAIL}).status_code == 202
        )
    assert env.client.post("/auth/password-reset/start", json={"email": EMAIL}).status_code == 429


def test_login_failures_are_limited_per_login(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    browser = env.browser()
    for _ in range(10):
        resp = browser.post(
            "/auth/login", json={"login": "Quiet-Heron", "password": "wrong-password"}
        )
        assert resp.status_code == 401
    # Locked for a while, even with the right password, and by email too: the account has one
    # budget however it is named.
    locked = browser.post("/auth/login", json={"login": "quiet-heron", "password": PASSWORD})
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) <= 15 * 60
    by_email = browser.post("/auth/login", json={"login": EMAIL, "password": PASSWORD})
    assert by_email.status_code == 429
    # Other accounts are unaffected.
    env.signup("calm-otter", client=env.browser())
    other = browser.post("/auth/login", json={"login": "calm-otter", "password": PASSWORD})
    assert other.status_code == 200
    # When the window ends the account can log in again.
    env.redis.delete(*env.redis.keys("rl:login-fail:*"))
    assert (
        browser.post("/auth/login", json={"login": EMAIL, "password": PASSWORD}).status_code == 200
    )


def test_username_and_email_share_one_login_failure_budget(env: Env) -> None:
    env.signup("quiet-heron", EMAIL)
    browser = env.browser()
    for n in range(10):
        ident = "quiet-heron" if n % 2 else EMAIL
        resp = browser.post("/auth/login", json={"login": ident, "password": "wrong-password"})
        assert resp.status_code == 401
    for ident in ("quiet-heron", EMAIL):
        resp = browser.post("/auth/login", json={"login": ident, "password": PASSWORD})
        assert resp.status_code == 429


def test_login_attempt_is_counted_before_the_password_is_checked(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent guesses cannot race past the limit: by the time the slow hash runs, the
    attempt is already in both counters."""
    from api.routers import auth as auth_router

    env.signup("quiet-heron", EMAIL)
    seen: list[list[int]] = []
    real = auth_router.verify_password

    def spy(stored: str | None, password: str) -> bool:
        seen.append(sorted(int(env.redis.get(k)) for k in env.redis.keys("rl:login-fail:*")))
        return real(stored, password)

    monkeypatch.setattr(auth_router, "verify_password", spy)
    browser = env.browser()
    bad = browser.post("/auth/login", json={"login": "quiet-heron", "password": "wrong-password"})
    assert bad.status_code == 401 and seen[-1] == [1, 1]  # the login and the account
    good = browser.post("/auth/login", json={"login": "quiet-heron", "password": PASSWORD})
    assert good.status_code == 200 and seen[-1] == [2, 2]
    # A good login gives its attempt back; the failure stays counted.
    assert sorted(int(env.redis.get(k)) for k in env.redis.keys("rl:login-fail:*")) == [1, 1]
    # Unknown logins are counted too (per typed login only).
    browser.post("/auth/login", json={"login": "nobody-here", "password": "wrong-password"})
    assert len(env.redis.keys("rl:login-fail:*")) == 3


def wrong_codes_until_the_address_is_locked(env: Env, path: str, extra: dict[str, str]) -> None:
    """Uses up the day's wrong codes for EMAIL across several emailed codes."""
    start_path = "/auth/email" if path == "/auth/verify-code" else "/auth/password-reset/start"
    wrong = 0
    while wrong < 10:
        pending_id = env.client.post(start_path, json={"email": EMAIL}).json()["pending_id"]
        good = env.outbox.last().code
        bad = "000000" if good != "000000" else "111111"
        for _ in range(min(codes.MAX_ATTEMPTS - 1, 10 - wrong)):
            resp = env.client.post(path, json={"pending_id": pending_id, "code": bad, **extra})
            assert resp.status_code == 400, resp.text
            wrong += 1


@pytest.mark.parametrize(
    ("path", "extra"),
    [
        ("/auth/verify-code", {}),
        ("/auth/password-reset/finish", {"new_password": "a brand new password"}),
    ],
)
def test_wrong_codes_are_capped_per_address_per_day(
    env: Env, path: str, extra: dict[str, str]
) -> None:
    reset = path != "/auth/verify-code"
    if reset:
        env.signup("quiet-heron", EMAIL)
    start_path = "/auth/password-reset/start" if reset else "/auth/email"
    wrong_codes_until_the_address_is_locked(env, path, extra)
    env.redis.delete(*env.redis.keys("rl:*-start:*"))  # an hour later: new codes can be sent

    # A fresh code, and the right one: refused, and the record is destroyed.
    pending_id = env.client.post(start_path, json={"email": EMAIL}).json()["pending_id"]
    good = env.outbox.last().code
    body = {"pending_id": pending_id, "code": good, **extra}
    live = len(env.redis.keys("auth:pending:*"))
    locked = env.client.post(path, json=body)
    assert locked.status_code == 429 and 0 < int(locked.headers["retry-after"]) <= 24 * 3600
    assert len(env.redis.keys("auth:pending:*")) == live - 1
    assert env.redis.keys("auth:ticket:*") == []
    assert env.client.post(path, json=body).status_code == 400
    if reset:  # the password did not change
        login = env.browser().post("/auth/login", json={"login": EMAIL, "password": PASSWORD})
        assert login.status_code == 200

    # Other addresses are unaffected.
    if not reset:
        env.verified_ticket("someone-else@uchicago.edu")

    # After the window passes, a new code works again.
    env.redis.delete(*env.redis.keys("rl:code-fail:*"))
    pending_id = env.client.post(start_path, json={"email": EMAIL}).json()["pending_id"]
    body = {"pending_id": pending_id, "code": env.outbox.last().code, **extra}
    assert env.client.post(path, json=body).status_code in (200, 204)


def test_a_correct_code_does_not_use_up_the_address_budget(env: Env) -> None:
    pending_id = start(env)
    good = env.outbox.last().code
    assert good is not None
    bad = "000000" if good != "000000" else "111111"
    env.client.post("/auth/verify-code", json={"pending_id": pending_id, "code": bad})
    resp = env.client.post("/auth/verify-code", json={"pending_id": pending_id, "code": good})
    assert resp.status_code == 200
    (key,) = env.redis.keys("rl:code-fail:*")
    assert env.redis.get(key) == "1" and 0 < env.redis.ttl(key) <= 24 * 3600
    assert EMAIL not in key


def test_code_cap_does_not_reveal_whether_the_address_has_an_account(env: Env) -> None:
    """A sign-up for a taken address and a reset for an unknown one make "dead" records; wrong
    codes against them count for the address just like against a live record."""
    env.signup("quiet-heron", EMAIL)
    fresh = env.browser()
    statuses: dict[str, list[int]] = {}
    for label, start_path, email in (
        ("dead", "/auth/email", EMAIL),
        ("live", "/auth/email", "calm-otter@uchicago.edu"),
    ):
        statuses[label] = []
        for _ in range(3):
            pending_id = fresh.post(start_path, json={"email": email}).json()["pending_id"]
            for _ in range(4):
                resp = fresh.post(
                    "/auth/verify-code", json={"pending_id": pending_id, "code": "000000"}
                )
                statuses[label].append(resp.status_code)
    if "000000" not in [m.code for m in env.outbox.sent]:
        assert statuses["dead"] == statuses["live"] == [400] * 10 + [429, 400]


@pytest.mark.parametrize(
    ("method", "path", "body", "per_day"),
    [
        ("post", "/auth/email", {"email": "x"}, 40),
        ("post", "/auth/verify-code", {"pending_id": "x", "code": "123456"}, 100),
        ("post", "/auth/register", {"ticket": "x", "username": "abc", "password": PASSWORD}, 40),
        ("post", "/auth/login", {"login": "abc", "password": "x"}, 300),
        ("post", "/auth/logout", None, 600),
        ("post", "/auth/password-reset/start", {"email": "x"}, 40),
        (
            "post",
            "/auth/password-reset/finish",
            {"pending_id": "x", "code": "123456", "new_password": PASSWORD},
            100,
        ),
        ("get", "/account/export", None, 600),
        ("post", "/account/password", {"current_password": "x", "new_password": PASSWORD}, 600),
        ("post", "/account/delete", {"password": "x", "posts": "keep"}, 600),
    ],
)
def test_every_auth_endpoint_has_an_ip_limit(
    env: Env, method: str, path: str, body: dict[str, str] | None, per_day: int
) -> None:
    # Fill the caller's counter up to the limit, then one more request must be refused.
    first = env.client.request(method.upper(), path, json=body)
    assert first.status_code != 429
    (key,) = (k for k in env.redis.keys("rl:*:ip:*"))
    assert 0 < env.redis.ttl(key) <= 24 * 3600  # Redis-only, gone within 24 hours
    assert "testclient" not in key
    env.redis.set(key, per_day, keepttl=True)
    blocked = env.client.request(method.upper(), path, json=body)
    assert blocked.status_code == 429 and "retry-after" in blocked.headers


def test_session_endpoint_has_an_ip_limit(env: Env) -> None:
    env.client.get("/auth/session")
    (key,) = env.redis.keys("rl:session:ip:*")
    env.redis.set(key, 20000, keepttl=True)
    assert env.client.get("/auth/session").status_code == 429


def test_ip_limit_uses_the_forwarded_address_only_behind_a_trusted_proxy(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def count() -> int:
        return len(env.redis.keys("rl:login:ip:*"))

    body = {"login": "abc", "password": "x"}
    env.client.post("/auth/login", json=body, headers={"X-Forwarded-For": "198.51.100.1"})
    env.client.post("/auth/login", json=body, headers={"X-Forwarded-For": "198.51.100.2"})
    assert count() == 1  # header ignored: a client cannot dodge the limit by spoofing it
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
    env.client.post("/auth/login", json=body, headers={"X-Forwarded-For": "6.6.6.6, 198.51.100.1"})
    env.client.post("/auth/login", json=body, headers={"X-Forwarded-For": "7.7.7.7, 198.51.100.1"})
    env.client.post("/auth/login", json=body, headers={"X-Forwarded-For": "198.51.100.2"})
    assert count() == 3


# ------------------------------------------------------------------------------- privacy


def test_no_email_or_ip_reaches_logs_and_email_reaches_only_account_email(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Runs every flow with all logging on (including SQL statements and their parameters) and
    a client IP, then searches the logs, stdout/stderr, Redis and every database column."""
    email, local, ip = "Secret.Student@uchicago.edu", "secret.student", "203.0.113.77"
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
    caplog.set_level(logging.DEBUG)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    env.client.headers["X-Forwarded-For"] = ip
    try:
        session = env.signup("quiet-heron", email)
        env.client.post("/auth/email", json={"email": email})  # already registered
        env.client.post("/auth/email", json={"email": "not an email " + email + ".evil.com"})
        env.client.post("/auth/logout", headers=csrf(session))
        env.client.post("/auth/login", json={"login": email, "password": "wrong-password"})
        env.client.post("/auth/login", json={"login": email, "password": PASSWORD})
        started = env.client.post("/auth/password-reset/start", json={"email": email})
        env.client.post(
            "/auth/password-reset/finish",
            json={
                "pending_id": started.json()["pending_id"],
                "code": env.outbox.last().code,
                "new_password": "a brand new password",
            },
        )
        login = env.client.post(
            "/auth/login", json={"login": email, "password": "a brand new password"}
        )
        assert login.status_code == 200
        assert env.client.get("/account/export").status_code == 200
        env.verified_ticket("pending.person@uchicago.edu", env.browser())  # left in Redis
        logging.getLogger("uvicorn.error").error("unhandled for %s from %s", email, ip)
    finally:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    captured = capfd.readouterr()
    logs = "\n".join(
        [caplog.text, captured.out, captured.err, *(r.getMessage() for r in caplog.records)]
    ).lower()
    assert "insert into account" in logs  # SQL logging really was on
    assert "[email]" in logs
    for secret in (email.lower(), local, "pending.person", ip, "@uchicago", "%40"):
        assert secret not in logs, secret

    # Redis: no IP anywhere; an email only in the 10-minute ticket of the unfinished sign-up.
    dump = env.redis_dump().lower()
    assert ip not in dump and local not in dump
    holders = [line for line in dump.splitlines() if "pending.person" in line]
    assert len(holders) == 1 and holders[0].startswith("auth:ticket:")

    # Database: the address is in account.email and in no other column of any table.
    found = []
    insp = inspect(env.engine)
    with env.db() as db:
        for table in insp.get_table_names():
            for row in db.execute(text(f'SELECT * FROM "{table}"')).mappings():
                for column, value in row.items():
                    text_value = str(value).lower()
                    assert ip not in text_value
                    if local in text_value or "@" in text_value:
                        found.append((table, column))
    assert found == [("account", "email")]
