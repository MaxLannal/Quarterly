"""Helpers for the auth and account tests: one migrated throwaway database per test module,
a fresh fakeredis and app per test, and a capturing email backend."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import fakeredis
import pytest
from alembic import command
from api.auth.emails import OutgoingEmail, get_email_backend
from api.config import get_settings
from api.db.base import Base
from api.db.session import get_session
from api.main import create_app
from api_test_support import alembic_config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "correct horse battery"
ORIGIN = "https://testserver"  # https, so the client keeps Secure cookies


@contextmanager
def migrated_database() -> Iterator[str]:
    base = make_url(get_settings().database_url)
    name = f"qp_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as exc:
        admin.dispose()
        if os.environ.get("QP_ALLOW_NO_DB"):
            pytest.skip(f"no database server: {exc}")
        raise
    url = base.set(database=name).render_as_string(hide_password=False)
    try:
        command.upgrade(alembic_config(url), "head")
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


class Outbox:
    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    def send(self, message: OutgoingEmail) -> None:
        self.sent.append(message)

    def last(self) -> OutgoingEmail:
        return self.sent[-1]


@dataclass
class Env:
    app: FastAPI
    engine: Engine
    redis: Any
    outbox: Outbox
    client: TestClient
    _clients: list[TestClient] = field(default_factory=list)

    def browser(self) -> TestClient:
        """Another browser (its own cookie jar) talking to the same app."""
        client = TestClient(self.app, base_url=ORIGIN)
        self._clients.append(client)
        return client

    def db(self) -> Session:
        return Session(self.engine)

    def verified_ticket(self, email: str, client: TestClient | None = None) -> str:
        client = client or self.client
        started = client.post("/auth/email", json={"email": email})
        assert started.status_code == 202, started.text
        message = self.outbox.last()
        assert message.code is not None
        verified = client.post(
            "/auth/verify-code",
            json={"pending_id": started.json()["pending_id"], "code": message.code},
        )
        assert verified.status_code == 200, verified.text
        return str(verified.json()["ticket"])

    def signup(
        self,
        username: str = "quiet-heron",
        email: str | None = None,
        password: str = PASSWORD,
        client: TestClient | None = None,
    ) -> dict[str, Any]:
        """Runs steps 1-3; the client ends up logged in. Returns SessionOut."""
        client = client or self.client
        ticket = self.verified_ticket(email or f"{username}@uchicago.edu", client)
        resp = client.post(
            "/auth/register", json={"ticket": ticket, "username": username, "password": password}
        )
        assert resp.status_code == 201, resp.text
        body: dict[str, Any] = resp.json()
        return body

    def redis_dump(self) -> str:
        """Every key and value in Redis, as text."""
        parts = []
        for key in self.redis.keys("*"):
            kind = self.redis.type(key)
            value = self.redis.smembers(key) if kind == "set" else self.redis.get(key)
            parts.append(f"{key}={value}")
        return "\n".join(parts)


def csrf(session_out: dict[str, Any]) -> dict[str, str]:
    return {"X-CSRF-Token": session_out["csrf_token"]}


@contextmanager
def auth_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    settings = get_settings()
    # Independent of the developer's .env.
    monkeypatch.setattr(settings, "session_cookie_secure", True)
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    monkeypatch.setattr(settings, "environment", "development")
    engine = create_engine(db_url)
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    app = create_app()
    app.state.redis = fakeredis.FakeRedis(decode_responses=True)
    outbox = Outbox()
    factory = sessionmaker(engine)

    def db_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = db_session
    app.dependency_overrides[get_email_backend] = lambda: outbox
    env = Env(
        app=app,
        engine=engine,
        redis=app.state.redis,
        outbox=outbox,
        client=TestClient(app, base_url=ORIGIN),
    )
    try:
        yield env
    finally:
        env.client.close()
        for client in env._clients:
            client.close()
        engine.dispose()
