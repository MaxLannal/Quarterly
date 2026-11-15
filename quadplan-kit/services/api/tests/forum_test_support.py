"""Helpers for the forum tests: a catalog with three forum pages, accounts that are logged in
in their own browsers, and a scripted FakeLLM for the A4 classifier."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from api.db import models as m
from auth_test_support import Env, auth_env, csrf
from fastapi.testclient import TestClient
from llm_gateway.api import FakeLLM, get_llm
from sqlalchemy import update

YEAR = "2099-00"


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


@dataclass
class ForumEnv:
    env: Env
    llm: FakeLLM
    pages: dict[str, int] = field(default_factory=dict)
    _n: int = 0

    def user(self, name: str | None = None) -> User:
        self._n += 1
        name = name or f"student-{self._n}"
        client = self.env.browser()
        session = self.env.signup(username=name, client=client)
        return User(client=client, session=session)

    def admin(self) -> User:
        user = self.user("the-admin")
        with self.env.db() as db:
            db.execute(
                update(m.Account).where(m.Account.username == "the-admin").values(role="admin")
            )
            db.commit()
        return user

    def hold(self, target_type: str, target_id: int, label: str = "identifying_info") -> None:
        """Mark an item held by the model, as an earlier version of the forum did on submit
        (posts now publish at once, P08-1), to test how held items are shown and moderated."""
        with self.env.db() as db:
            model = m.Post if target_type == "post" else m.Comment
            db.execute(update(model).where(model.id == target_id).values(status="held"))
            db.add(
                m.ModerationAction(
                    target_type=target_type,
                    target_id=target_id,
                    action="hold",
                    reason=label,
                    actor="model",
                )
            )
            db.commit()


def seed_pages(env: Env) -> dict[str, int]:
    """Two courses, two instructors, three pages; sections place them in terms."""
    with env.db() as db:
        db.add(m.CatalogYear(id=YEAR))
        db.add_all([m.Term(id=t, year=int(t[:4]), quarter=t[5:]) for t in ("2099-AU", "2100-WI")])
        db.flush()
        a = m.Course(
            catalog_year=YEAR, subject="TEST", number="10100", code="TEST 10100", title="Fake Intro"
        )
        b = m.Course(
            catalog_year=YEAR,
            subject="TEST",
            number="20100",
            code="TEST 20100",
            title="Fake Theory",
        )
        doe = m.Instructor(slug="jane-doe", display_name="Jane Doe", department="Fake Dept")
        roe = m.Instructor(slug="rick-roe", display_name="Rick Roe")
        db.add_all([a, b, doe, roe])
        db.flush()
        pages = {
            "a_doe": m.CourseInstructor(
                course_id=a.id,
                instructor_id=doe.id,
                first_term="2099-AU",
                last_term="2099-AU",
                n_terms=1,
            ),
            "a_roe": m.CourseInstructor(
                course_id=a.id,
                instructor_id=roe.id,
                first_term="2100-WI",
                last_term="2100-WI",
                n_terms=1,
            ),
            "b_doe": m.CourseInstructor(
                course_id=b.id,
                instructor_id=doe.id,
                first_term="2099-AU",
                last_term="2100-WI",
                n_terms=2,
            ),
        }
        db.add_all(pages.values())
        db.add(
            m.Section(term_id="2100-WI", course_id=b.id, section_no="1", instructor_ids=[doe.id])
        )
        db.commit()
        return {k: v.id for k, v in pages.items()}


@contextmanager
def forum_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[ForumEnv]:
    # Independent of the developer's .env.
    with auth_env(db_url, monkeypatch) as env:
        llm = FakeLLM()
        env.app.dependency_overrides[get_llm] = lambda: llm
        fenv = ForumEnv(env=env, llm=llm)
        fenv.pages = seed_pages(env)
        yield fenv


REVIEW = {
    "kind": "review",
    "body_md": "Clear lectures, hard problem sets.",
    "term_taken": "2099-AU",
    "ratings": {
        "overall": 4,
        "difficulty": 3,
        "intellectual_intensity": 4,
        "workload_hours": 9,
        "would_recommend": True,
    },
}


def discussion(
    title: str = "Is the midterm curved?", body: str = "Asking for a friend."
) -> dict[str, Any]:
    return {"kind": "discussion", "title": title, "body_md": body}
