"""What is new for the student (`GET /me/updates`, `POST /me/updates/seen`) on the fake 2099-00
fixture: followed threads, replies to the student's own question, followed courses, interest
matches, the high-water marks and login. The digest and the route courses went in issue #15."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.commons.identity import commons_ref
from api.config import get_settings
from api.db import models as m
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from auth_test_support import Env, auth_env, csrf, migrated_database

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    monkeypatch.setattr(get_settings(), "show_unpublished_programs", True)
    with auth_env(db_url, monkeypatch) as e:
        with e.db() as db:
            upsert_bundle(db, load_bundle(FIXTURES / "seed" / "2099-00"))
        yield e


def login(env: Env, name: str = "quiet-heron") -> tuple[dict[str, str], uuid.UUID]:
    session = env.signup(name)
    return csrf(session), uuid.UUID(session["account"]["id"])


def course_id(env: Env, code: str) -> int:
    with env.db() as db:
        found = db.scalar(
            sa.select(m.Course.id).where(m.Course.code == code, m.Course.catalog_year == "2099-00")
        )
        assert found is not None
        return int(found)


def thread(env: Env, title: str, *, code: str | None = None, author: str = "someone") -> int:
    with env.db() as db:
        row = m.CommonsThread(
            title=title,
            body_md=f"**Body** of {title}. Mail me at jane@uchicago.edu",
            author_ref=author,
            course_id=course_id(env, code) if code else None,
        )
        db.add(row)
        db.commit()
        return int(row.id)


def reply(
    env: Env, thread_id: int, text: str, *, author: str = "other", kind: str = "human"
) -> int:
    with env.db() as db:
        row = m.CommonsReply(thread_id=thread_id, body_md=text, author_ref=author, kind=kind)
        db.add(row)
        db.commit()
        return int(row.id)


def profile(env: Env, account_id: uuid.UUID, **fields: Any) -> None:
    with env.db() as db:
        db.merge(m.StudentProfile(account_id=account_id, **fields))
        db.commit()


def get(env: Env, headers: dict[str, str]) -> dict[str, Any]:
    resp = env.client.get("/me/updates", headers=headers)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


def by_key(body: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    return {(i["kind"], i["id"]): i for i in body["items"]}


def test_logged_out_is_refused(env: Env) -> None:
    assert env.client.get("/me/updates").status_code == 401
    assert env.client.post("/me/updates/seen", json={}).status_code == 401


def test_a_followed_thread_shows_its_new_reply_and_seen_moves_the_mark(env: Env) -> None:
    headers, me = login(env)
    followed = thread(env, "Which calculus first?")
    profile(env, me, follows={"threads": [followed]})
    first = reply(env, followed, "Start with *the honors one*. Call 773-702-1234.")
    items = by_key(get(env, headers))
    item = items[("reply", first)]
    assert item["reason"] == "On a thread you follow" and item["is_new"] is True
    assert item["href"] == f"/forum/t/{followed}#reply-{first}"
    assert item["snippet"] == "Start with the honors one. Call [phone removed]."

    seen = env.client.post("/me/updates/seen", headers=headers)
    assert seen.status_code == 200 and seen.json()["reply"] == first
    after = get(env, headers)
    assert by_key(after)[("reply", first)]["is_new"] is False and after["unread"] == 0

    second = reply(env, followed, "Or the regular one.")
    later = by_key(get(env, headers))
    assert later[("reply", second)]["is_new"] is True
    assert later[("reply", first)]["is_new"] is False
    # Marks never move backwards, and an explicit mark is honoured.
    back = env.client.post("/me/updates/seen", json={"reply": 0}, headers=headers)
    assert back.json()["reply"] == first
    with env.db() as db:
        row = db.get(m.StudentProfile, me)
        assert row is not None and row.updates_seen["reply"] == first


def test_replies_to_my_own_question_and_not_my_own_replies(env: Env) -> None:
    headers, me = login(env)
    with env.db() as db:
        mine = m.CommonsThread(title="Is TEST 20000 hard?", body_md="Asking.", author_ref="x")
        db.add(mine)
        db.flush()
        mine.author_ref = commons_ref(me, mine.id)
        db.commit()
        mine_id = int(mine.id)
    answer = reply(env, mine_id, "Not too hard.")
    own = reply(env, mine_id, "Thanks!", author=commons_ref(me, mine_id))
    bot = reply(env, mine_id, "The bot's take.", kind="bot", author="bot")
    items = by_key(get(env, headers))
    assert items[("reply", answer)]["reason"] == "A reply to your question"
    assert items[("reply", bot)]["title"].startswith("The forum bot answered")
    assert ("reply", own) not in items and ("thread", mine_id) not in items


def test_followed_courses_and_interest_matches(env: Env) -> None:
    headers, me = login(env)
    profile(
        env,
        me,
        research_areas=["Cross-listed things", "quantum computing"],
        follows={"courses": ["TEST 10100", "TEST 20000"]},
    )
    advanced = thread(env, "Advanced advice", code="TEST 20000")
    followed = thread(env, "Intro II advice", code="TEST 10100")
    quantum = thread(env, "Any quantum courses for first-years?")
    crosslisted = thread(env, "Help", code="TEST 20100")  # course title "Fake Cross-listed"
    unrelated = thread(env, "Where to eat?")
    items = by_key(get(env, headers))
    assert items[("thread", advanced)]["reason"] == "About TEST 20000, a course you follow"
    assert items[("thread", followed)]["reason"] == "About TEST 10100, a course you follow"
    assert items[("thread", followed)]["course_code"] == "TEST 10100"
    assert items[("thread", quantum)]["reason"] == "Matches your interest in quantum computing"
    assert ("thread", unrelated) not in items  # enough personal items: no general filler
    assert (
        items[("thread", crosslisted)]["reason"] == "Matches your interest in Cross-listed things"
    )
    snippet = items[("thread", quantum)]["snippet"]
    assert "jane@" not in snippet and "**" not in snippet


def test_new_on_quarterly_fills_in_and_forum_posts_link_to_their_page(env: Env) -> None:
    headers, _ = login(env)
    general = thread(env, "Best study spots?")
    with env.db() as db:
        teacher = m.Instructor(slug="fake-teacher", display_name="Fake Teacher")
        db.add(teacher)
        db.flush()
        page = m.CourseInstructor(course_id=course_id(env, "TEST 10000"), instructor_id=teacher.id)
        db.add(page)
        db.flush()
        post = m.Post(
            course_instructor_id=page.id,
            kind="review",
            author_ref="r",
            body_md="Loved it.",
            status="visible",
            created_day=dt.date.today(),
        )
        db.add(post)
        db.commit()
        post_id = int(post.id)
    items = by_key(get(env, headers))
    assert items[("thread", general)]["reason"] == "New on Quarterly"
    review = items[("review", post_id)]
    assert review["href"] == f"/courses/TEST%2010000/i/fake-teacher/t/{post_id}"
    assert review["course_code"] == "TEST 10000"
    # A brand-new student: items from the last week count as new.
    assert review["is_new"] is True


def test_the_digest_option_is_gone(env: Env) -> None:
    # Issue #15: the companion's AI digest went; `?digest=true` is ignored and adds nothing.
    headers, _ = login(env)
    resp = env.client.get("/me/updates?digest=true", headers=headers)
    assert resp.status_code == 200 and "digest" not in resp.json()
