"""Helpers for the Commons tests (no tests here): a tiny 2026-27 catalog (the campus agents'
year), accounts logged in in their own browsers, and small request helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from api.agents.live import CAMPUS_YEAR
from api.db import models as m
from auth_test_support import Env, auth_env, csrf
from fastapi.testclient import TestClient
from llm_gateway.api import FakeLLM, get_llm

COURSES = (
    ("CMSC", "14100", "Introduction to Computer Science I"),
    ("CMSC", "14200", "Introduction to Computer Science II"),
    ("MATH", "15300", "Calculus III"),
    ("MATH", "16300", "Honors Calculus III"),
    ("PHYS", "14100", "Honors Mechanics"),
)


@dataclass
class User:
    client: TestClient
    session: dict[str, Any]

    @property
    def headers(self) -> dict[str, str]:
        return csrf(self.session)

    @property
    def account_id(self) -> str:
        return str(self.session["account"]["id"])

    def get(self, url: str, **kw: Any) -> Any:
        return self.client.get(url, **kw)

    def post(self, url: str, json: Any = None) -> Any:
        return self.client.post(url, json=json, headers=self.headers)

    def patch(self, url: str, json: Any = None) -> Any:
        return self.client.patch(url, json=json, headers=self.headers)

    def delete(self, url: str) -> Any:
        return self.client.delete(url, headers=self.headers)

    def ask(self, title: str, **extra: Any) -> dict[str, Any]:
        resp = self.post("/commons/threads", {"title": title, **extra})
        assert resp.status_code == 201, resp.text
        out: dict[str, Any] = resp.json()
        return out

    def reply(self, thread_id: int, body: str, parent: int | None = None) -> dict[str, Any]:
        resp = self.post(
            f"/commons/threads/{thread_id}/replies", {"body_md": body, "parent_id": parent}
        )
        assert resp.status_code == 201, resp.text
        out: dict[str, Any] = resp.json()
        return out

    def thread(self, thread_id: int) -> dict[str, Any]:
        resp = self.get(f"/commons/threads/{thread_id}")
        assert resp.status_code == 200, resp.text
        out: dict[str, Any] = resp.json()
        return out


@dataclass
class CommonsEnv:
    env: Env
    llm: FakeLLM
    _n: int = 0
    users: list[User] = field(default_factory=list)

    def user(self, name: str | None = None) -> User:
        self._n += 1
        client = self.env.browser()
        session = self.env.signup(username=name or f"student-{self._n}", client=client)
        user = User(client=client, session=session)
        self.users.append(user)
        return user

    def anon(self) -> TestClient:
        return self.env.browser()

    def use(self, llm: FakeLLM) -> FakeLLM:
        self.llm = llm
        self.env.app.dependency_overrides[get_llm] = lambda: llm
        return llm


def seed_catalog(env: Env) -> None:
    with env.db() as db:
        db.add(m.CatalogYear(id=CAMPUS_YEAR))
        db.flush()
        for subject, number, title in COURSES:
            db.add(
                m.Course(
                    catalog_year=CAMPUS_YEAR,
                    subject=subject,
                    number=number,
                    code=f"{subject} {number}",
                    title=title,
                    description=f"{title}: a course for the tests.",
                )
            )
        db.commit()


@contextmanager
def commons_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[CommonsEnv]:
    with auth_env(db_url, monkeypatch) as env:
        llm = FakeLLM()
        env.app.dependency_overrides[get_llm] = lambda: llm
        seed_catalog(env)
        yield CommonsEnv(env=env, llm=llm)


def walk(replies: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Every reply of a tree, depth first."""
    for reply in replies:
        yield reply
        yield from walk(reply["children"])
