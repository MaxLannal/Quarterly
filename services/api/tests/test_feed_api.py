"""The feed (`GET /feed`, `GET /feed/categories`) on a slice of the real 2026-27 catalog: mixed
kinds with real course codes only, Commons voices for everyone and forum posts only for logged-in
readers, personal ranking, Explore, Following, categories and the cursor."""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
import yaml
from api.db import models as m
from auth_test_support import Env, auth_env, migrated_database
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "seed" / "2026-27" / "courses"
YEAR = "2026-27"
#: Seed files to load, and how many of their courses (with a description) to take.
FILES = {
    "CMSC": 60, "MATH": 30, "PHYS": 8, "ECON": 30, "HUMA": 30, "CLCV": 7, "HIST": 30,
    "BIOS": 30, "MUSI": 9, "GEOS": 6, "EALC": 8, "ARTH": 20, "SOSC": 30, "CRWR": 25,
    "RLST": 25, "LING": 15, "CHEM": 15, "STAT": 15, "MENG": 2, "PHSC": 10, "SPAN": 1,
}  # fmt: skip
QUANTUM = "CMSC 19928"  # "Quantum Computing: An Introduction"


def seed_catalog(env: Env) -> dict[str, int]:
    """A slice of the real catalog (every course text verbatim from data/seed); code -> id."""
    rows: list[dict[str, Any]] = []
    for name, limit in FILES.items():
        courses = yaml.safe_load((SEED / f"{name}.yaml").read_text())["courses"]
        taken = 0
        for c in courses:
            wanted = "quantum" in str(c["title"]).lower() or taken < limit
            if not c.get("description") or not wanted:
                continue
            subject, number = str(c["code"]).split()
            rows.append(
                {
                    "catalog_year": YEAR,
                    "subject": subject,
                    "number": number,
                    "code": str(c["code"]),
                    "title": " ".join(str(c["title"]).split()),
                    "units": int(c.get("units", 100)),
                    "description": " ".join(str(c["description"]).split()),
                    "core_tags": list(c.get("core_tags") or []),
                }
            )
            taken += 1
    with env.db() as db:
        db.add(m.CatalogYear(id=YEAR))
        db.flush()
        db.execute(sa.insert(m.Course), rows)
        db.add_all(
            [
                m.Program(id="cmsc-bs", name="Computer Science (BS)", type="major",
                          department="Computer Science"),
                m.Program(id="core", name="The Core (general education)", type="core",
                          department="The College"),
            ]
        )  # fmt: skip
        db.commit()
        return dict(db.execute(sa.select(m.Course.code, m.Course.id)).tuples().all())


def add_voices(env: Env, codes: dict[str, int]) -> dict[str, int]:
    """A Commons question with a human reply, a bot reply and a removed reply; an open question;
    and a forum review. Returns their ids."""
    first_cmsc = sorted(c for c in codes if c.startswith("CMSC"))[0]
    with env.db() as db:
        thread = m.CommonsThread(
            course_id=codes[QUANTUM],
            author_ref="ref-asker",
            title="Is the quantum course OK without physics?",
            body_md="I have **no** physics. Is that fine?",
            reply_count=3,
        )
        open_question = m.CommonsThread(
            course_id=codes[first_cmsc],
            author_ref="ref-asker-2",
            title="Which section of intro CS is calmer?",
            body_md="Asking for a friend.",
        )
        db.add_all([thread, open_question])
        db.flush()
        human = m.CommonsReply(
            thread_id=thread.id,
            author_ref="ref-helper",
            body_md="Yes, **totally**: the first weeks teach the linear algebra. Mail me at "
            "kid@uchicago.edu",
        )
        bot = m.CommonsReply(thread_id=thread.id, kind="bot", body_md="I am the bot answer.")
        gone = m.CommonsReply(
            thread_id=thread.id, author_ref="ref-x", body_md="Removed words", status="removed"
        )
        db.add_all([human, bot, gone])
        db.add(
            m.CommonsPseudonym(thread_id=thread.id, author_ref="ref-helper", handle="Witty Trout")
        )
        teacher = m.Instructor(slug="fake-teacher", display_name="Fake Teacher")
        db.add(teacher)
        db.flush()
        page = m.CourseInstructor(course_id=codes[first_cmsc], instructor_id=teacher.id)
        db.add(page)
        db.flush()
        pseudonym = m.Pseudonym(author_ref="ref-reviewer", course_instructor_id=page.id,
                                handle="Quiet Owl")  # fmt: skip
        db.add(pseudonym)
        db.flush()
        post = m.Post(
            course_instructor_id=page.id,
            kind="review",
            author_ref="ref-reviewer",
            pseudonym_id=pseudonym.id,
            title="Loved it",
            body_md="The problem sets were long but *fair*.",
            term_taken="2025-AU",
        )
        db.add(post)
        db.commit()
        return {
            "thread": thread.id,
            "open": open_question.id,
            "human": human.id,
            "bot": bot.id,
            "gone": gone.id,
            "post": post.id,
            "page_code": 0,
        }


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    with auth_env(db_url, monkeypatch) as e:
        e.codes = seed_catalog(e)  # type: ignore[attr-defined]
        yield e


def codes_of(env: Env) -> dict[str, int]:
    found: dict[str, int] = env.codes  # type: ignore[attr-defined]
    return found


def account_id(env: Env, username: str) -> uuid.UUID:
    with env.db() as db:
        found = db.scalar(sa.select(m.Account.id).where(m.Account.username == username))
        assert found is not None
        return found


def set_profile(env: Env, username: str, **fields: Any) -> None:
    with env.db() as db:
        db.merge(m.StudentProfile(account_id=account_id(env, username), **fields))
        db.commit()


def feed(client: TestClient, **params: Any) -> dict[str, Any]:
    resp = client.get("/feed", params=params)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


def all_items(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    for _ in range(20):
        page = (
            feed(client, limit=24, cursor=cursor, **params)
            if cursor
            else feed(client, limit=24, **params)
        )
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert cursor is None, "the feed should end"
    return items


def course_codes(item: dict[str, Any]) -> list[str]:
    kind = item["kind"]
    if kind == "course":
        return [item["code"], *[]]
    if kind in ("comment",):
        return [item["course"]["code"]]
    if kind == "question":
        return [item["course"]["code"]] if item["course"] else []
    if kind == "book":
        return [c["code"] for c in item["courses"]]
    return []


# ----------------------------------------------------------------------------- categories


def test_categories_cover_every_subject_in_the_database(env: Env) -> None:
    resp = env.client.get("/feed/categories")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 12 <= len(body["categories"]) <= 16 and body["selected"] == []
    listed = [s for c in body["categories"] for s in c["subjects"]]
    with env.db() as db:
        in_db = set(db.scalars(sa.select(m.Course.subject).distinct()))
    assert sorted(listed) == sorted(in_db)
    by_key = {c["key"]: c for c in body["categories"]}
    assert "CMSC" in by_key["computing"]["subjects"] and by_key["computing"]["course_count"] > 0
    assert all(c["blurb"] and c["motif"] for c in body["categories"])


def test_categories_show_the_saved_focus(env: Env) -> None:
    env.signup("quiet-heron")
    set_profile(env, "quiet-heron", feed_categories=["math", "unknown-key", "literature"])
    body = env.client.get("/feed/categories").json()
    assert body["selected"] == ["math", "literature"]


# ----------------------------------------------------------------------------- the feed


def test_the_feed_mixes_kinds_and_names_only_real_courses(env: Env) -> None:
    add_voices(env, codes_of(env))
    page = feed(env.client, limit=24)
    kinds = [i["kind"] for i in page["items"]]
    assert kinds[0] == "course" and len(kinds) == 24
    assert {"course", "book", "comment", "words", "question", "program"} <= set(kinds)
    assert page["headline"].startswith("Today's river: ") and len(page["headline"]) <= 90
    assert page["personalized"] is False and page["next_cursor"]
    real = set(codes_of(env))
    for item in page["items"]:
        assert set(course_codes(item)) <= real, item
    courses = [i for i in page["items"] if i["kind"] == "course"]
    for c in courses:
        assert len(c["excerpt"]) <= 300 and c["reason"]
        assert c["id"] == f"course:{c['code']}"
        assert len(c["books"]) <= 2 and c["illustration"]["motif"]
        assert 0 <= c["illustration"]["palette"] <= 5
    # A card of another kind every 3 or 4 courses; no two courses of one category in a row.
    run = 0
    for kind in kinds:
        run = run + 1 if kind == "course" else 0
        assert run <= 4
    cats = [c["category"]["key"] for c in courses]
    assert all(a != b for a, b in itertools.pairwise(cats))
    words = next(i for i in page["items"] if i["kind"] == "words")
    assert 12 <= len(words["words"]) <= 30
    program = next(i for i in page["items"] if i["kind"] == "program")
    assert program["program_id"] in ("cmsc-bs", "core")


def test_logged_out_readers_see_commons_voices_but_no_forum_posts(env: Env) -> None:
    ids = add_voices(env, codes_of(env))
    comments = [i for i in all_items(env.client) if i["kind"] == "comment"]
    assert comments and {c["source"] for c in comments} == {"commons"}
    assert {c["id"] for c in comments} == {f"comment:commons:{ids['human']}"}  # no bot, no removed
    voice = comments[0]
    assert voice["handle"] == "Witty Trout" and voice["href"] == f"/forum/t/{ids['thread']}"
    assert "**" not in voice["snippet"] and "uchicago.edu" not in voice["snippet"]
    questions = [i for i in all_items(env.client) if i["kind"] == "question"]
    assert {q["thread_id"] for q in questions} == {ids["thread"], ids["open"]}
    assert questions[0]["thread_id"] == ids["open"]  # the unanswered one first


def test_logged_in_readers_also_see_forum_posts(env: Env) -> None:
    ids = add_voices(env, codes_of(env))
    env.signup("quiet-heron")
    comments = [i for i in all_items(env.client) if i["kind"] == "comment"]
    forum = [c for c in comments if c["source"] == "forum"]
    assert [c["id"] for c in forum] == [f"comment:post:{ids['post']}"]
    post = forum[0]
    code = post["course"]["code"]
    assert post["handle"] == "Quiet Owl" and post["voice"] == "review"
    assert post["href"] == f"/courses/{code.replace(' ', '%20')}/i/fake-teacher/t/{ids['post']}"
    assert post["snippet"].startswith("Loved it. The problem sets were long but fair.")


def test_for_you_ranks_a_course_matching_an_interest_first(env: Env) -> None:
    env.signup("quiet-heron")
    set_profile(env, "quiet-heron", interests=["quantum"])
    page = feed(env.client, limit=12)
    assert page["personalized"] is True
    courses = [i for i in page["items"] if i["kind"] == "course"]
    quantum = [c for c in courses if "quantum" in c["title"].lower()]
    assert quantum, [c["title"] for c in courses]
    assert courses[0]["reason"] == "Because you're into quantum"
    assert "quantum" in page["headline"]


def test_explore_is_not_for_you(env: Env) -> None:
    for_you = [i["id"] for i in feed(env.client, limit=24)["items"]]
    explore = feed(env.client, tab="explore", limit=24)
    assert [i["id"] for i in explore["items"]] != for_you
    reasons = {i["reason"] for i in explore["items"] if i["kind"] == "course"}
    assert all(r.startswith("Something new: ") for r in reasons)


def test_explore_leans_away_from_the_chosen_categories(env: Env) -> None:
    env.signup("quiet-heron")
    set_profile(env, "quiet-heron", feed_categories=["computing"])
    items = [i for i in all_items(env.client, tab="explore") if i["kind"] == "course"]
    first = items[:40]
    chosen = [i for i in first if i["category"]["key"] == "computing"]
    assert chosen and all(i["reason"].startswith("More from your focus") for i in chosen)
    assert len(chosen) < len(first) / 4


def test_pages_never_repeat_an_item_and_the_stream_ends(env: Env) -> None:
    add_voices(env, codes_of(env))
    for tab in ("for_you", "explore"):
        items = all_items(env.client, tab=tab)
        ids = [i["id"] for i in items]
        assert len(ids) == len(set(ids)) and len(ids) > 48
    first = feed(env.client, limit=5)
    second = feed(env.client, limit=5, cursor=first["next_cursor"])
    assert {i["id"] for i in first["items"]}.isdisjoint(i["id"] for i in second["items"])
    broken = feed(env.client, limit=5, cursor="not-a-cursor")
    assert [i["id"] for i in broken["items"]] == [i["id"] for i in first["items"]]


def test_categories_filter_the_courses(env: Env) -> None:
    page = feed(env.client, limit=24, categories="math,nope")
    assert page["categories_applied"] == ["math"]
    courses = [i for i in page["items"] if i["kind"] == "course"]
    assert courses and {c["category"]["key"] for c in courses} == {"math"}
    assert all(c["reason"] == "In your focus: Mathematics & Statistics" for c in courses)


def test_the_saved_focus_applies_when_no_categories_are_sent(env: Env) -> None:
    env.signup("quiet-heron")
    set_profile(env, "quiet-heron", feed_categories=["literature"])
    page = feed(env.client, limit=12)
    assert page["categories_applied"] == ["literature"]
    assert {i["category"]["key"] for i in page["items"] if i["kind"] == "course"} == {"literature"}
    everything = feed(env.client, limit=12, categories="")
    assert everything["categories_applied"] == []


def test_following_is_empty_until_there_is_something_to_follow(env: Env) -> None:
    logged_out = feed(env.client, tab="following")
    assert logged_out["items"] == [] and logged_out["next_cursor"] is None
    env.signup("quiet-heron")
    empty = feed(env.client, tab="following")
    assert empty["items"] == [] and empty["next_cursor"] is None
    assert "follow" in empty["headline"].lower()


def test_following_shows_route_courses_and_their_commons_activity(env: Env) -> None:
    ids = add_voices(env, codes_of(env))
    env.signup("quiet-heron")
    with env.db() as db:
        db.add(
            m.Pathway(
                account_id=account_id(env, "quiet-heron"),
                title="The quantum track",
                courses=[{"code": QUANTUM, "title": "Quantum Computing", "year": 1}],
                status="chosen",
            )
        )
        db.add(m.Pathway(account_id=account_id(env, "quiet-heron"), title="Old", status="archived",
                         courses=[{"code": "MATH 13100", "year": 1}]))  # fmt: skip
        db.commit()
    items = feed(env.client, tab="following", limit=24)["items"]
    courses = [i for i in items if i["kind"] == "course"]
    assert [c["code"] for c in courses] == [QUANTUM]
    assert courses[0]["reason"] == "On your route 'The quantum track'"
    assert courses[0]["commons_count"] == 1
    voices = {i["id"] for i in items if i["kind"] in ("comment", "question")}
    assert f"comment:commons:{ids['human']}" in voices and f"question:{ids['thread']}" in voices
    assert f"question:{ids['open']}" not in voices  # about a course this student does not follow
