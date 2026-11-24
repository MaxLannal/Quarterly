"""The Catalog page's browse rows (`GET /catalog/browse`) and the course ratings
(`GET /course-ratings`), issue #19, on a slice of the real 2026-27 catalog: course spotlights
with real codes only, Commons quotes for everyone and forum quotes only for logged-in readers,
personal spotlights, newly released courses (the hand-written list and a second catalog year),
and ratings for logged-in students only. The Feed's endpoints are gone."""

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
from api.feed import new_courses as new_mod
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


def browse(client: TestClient) -> dict[str, Any]:
    resp = client.get("/catalog/browse")
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


@pytest.fixture
def no_listed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An empty hand-written list, so the real file does not change what a test sees."""
    path = tmp_path / "new_courses.yaml"
    path.write_text(yaml.safe_dump({"catalog_year": YEAR, "courses": []}))
    monkeypatch.setenv("NEW_COURSES_FILE", str(path))
    return path


# ----------------------------------------------------------------------------- the rows


def test_spotlights_name_only_real_courses_and_spread_the_categories(
    env: Env, no_listed: Path
) -> None:
    body = browse(env.client)
    assert body["catalog_year"] == YEAR and body["new_courses"] == []
    spotlights = body["spotlights"]
    assert len(spotlights) == 12
    real = set(codes_of(env))
    for c in spotlights:
        assert c["code"] in real and c["id"] == f"course:{c['code']}"
        assert c["reason"] and len(c["excerpt"]) <= 300
        assert c["illustration"]["motif"] and 0 <= c["illustration"]["palette"] <= 5
        assert "books" not in c and "words" not in c  # the shelf and the floating words went
    cats = [c["category"]["key"] for c in spotlights]
    assert all(a != b for a, b in itertools.pairwise(cats))
    # The same viewer on the same day gets the same row.
    assert [c["code"] for c in browse(env.client)["spotlights"]] == [c["code"] for c in spotlights]


def test_logged_out_readers_see_commons_quotes_but_no_forum_posts(
    env: Env, no_listed: Path
) -> None:
    ids = add_voices(env, codes_of(env))
    quotes = browse(env.client)["quotes"]
    assert [q["id"] for q in quotes] == [f"comment:commons:{ids['human']}"]  # no bot, no removed
    voice = quotes[0]
    assert voice["handle"] == "Witty Trout" and voice["href"] == f"/forum/t/{ids['thread']}"
    assert "**" not in voice["snippet"] and "uchicago.edu" not in voice["snippet"]


def test_logged_in_readers_also_see_forum_quotes(env: Env, no_listed: Path) -> None:
    ids = add_voices(env, codes_of(env))
    env.signup("quiet-heron")
    quotes = browse(env.client)["quotes"]
    forum = [q for q in quotes if q["source"] == "forum"]
    assert [q["id"] for q in forum] == [f"comment:post:{ids['post']}"]
    post = forum[0]
    code = post["course"]["code"]
    assert post["handle"] == "Quiet Owl" and post["voice"] == "review"
    assert post["href"] == f"/courses/{code.replace(' ', '%20')}/i/fake-teacher/t/{ids['post']}"
    assert post["snippet"].startswith("Loved it. The problem sets were long but fair.")


def test_spotlights_follow_the_students_interest_and_follows(env: Env, no_listed: Path) -> None:
    math = sorted(c for c in codes_of(env) if c.startswith("MATH"))[0]
    env.signup("quiet-heron")
    set_profile(env, "quiet-heron", interests=["quantum"], follows={"courses": [math]})
    spotlights = browse(env.client)["spotlights"]
    assert spotlights[0]["reason"] == "Because you're into quantum"
    assert "quantum" in spotlights[0]["title"].lower()
    followed = [c for c in spotlights if c["code"] == math]
    assert followed and followed[0]["reason"] == "You follow this course"


# ----------------------------------------------------------------------------- new courses


def test_new_courses_come_from_the_hand_written_list(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    listed = sorted(codes_of(env))[:2]
    path = tmp_path / "new_courses.yaml"
    entries = [
        {
            "code": code,
            "source": {"url": "https://example.invalid/new", "quote": f"Fake: {code} is new."},
        }
        for code in [*listed, "ZZZZ 99999"]  # the last is not in the catalog: not shown
    ]
    path.write_text(yaml.safe_dump({"catalog_year": YEAR, "courses": entries}))
    monkeypatch.setenv("NEW_COURSES_FILE", str(path))
    fresh = browse(env.client)["new_courses"]
    assert [c["code"] for c in fresh] == listed
    assert fresh[0]["basis"] == "listed" and fresh[0]["reason"] == f"New in {YEAR}"
    assert fresh[0]["source_quote"] == f"Fake: {listed[0]} is new."
    assert fresh[0]["source_url"] == "https://example.invalid/new"
    # A list for another catalog year is not used.
    path.write_text(yaml.safe_dump({"catalog_year": "2025-26", "courses": entries[:1]}))
    assert browse(env.client)["new_courses"] == []


def test_a_listed_course_needs_a_quote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "new_courses.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "catalog_year": YEAR,
                "courses": [{"code": "CMSC 14100", "source": {"url": "https://x.invalid/"}}],
            }
        )
    )
    monkeypatch.setenv("NEW_COURSES_FILE", str(path))
    with pytest.raises(ValueError, match="quote"):
        new_mod.load_listed(strict=True)
    assert new_mod.load_listed() is None  # the page then shows no listed course, and no error


def test_a_second_catalog_year_shows_what_is_new(env: Env, no_listed: Path) -> None:
    codes = sorted(codes_of(env))
    kept = codes[2:]  # the first two codes were not in the year before
    with env.db() as db:
        db.add(m.CatalogYear(id="2025-26"))
        db.flush()
        rows = db.scalars(sa.select(m.Course).where(m.Course.code.in_(kept))).all()
        db.execute(
            sa.insert(m.Course),
            [
                {
                    "catalog_year": "2025-26",
                    "subject": r.subject,
                    "number": r.number,
                    "code": r.code,
                    "title": r.title,
                    "units": r.units,
                }
                for r in rows
            ],
        )
        db.commit()
    fresh = browse(env.client)["new_courses"]
    assert [c["code"] for c in fresh] == codes[:2]
    assert {c["basis"] for c in fresh} == {"catalog"}
    assert fresh[0]["reason"] == "Not in the 2025-26 catalog" and fresh[0]["source_url"] is None


def test_a_small_or_empty_earlier_year_shows_nothing_as_new(env: Env, no_listed: Path) -> None:
    # A catalog_year row with few or no courses (one program's ingestion, one review batch) is
    # not a catalog: comparing with it would call most courses new.
    codes = sorted(codes_of(env))
    with env.db() as db:
        db.add(m.CatalogYear(id="2024-25"))
        db.add(m.CatalogYear(id="2025-26"))
        db.flush()
        row = db.scalars(sa.select(m.Course).where(m.Course.code == codes[0])).one()
        db.execute(
            sa.insert(m.Course),
            [
                {
                    "catalog_year": "2025-26",
                    "subject": row.subject,
                    "number": row.number,
                    "code": row.code,
                    "title": row.title,
                    "units": row.units,
                }
            ],
        )
        db.commit()
    assert browse(env.client)["new_courses"] == []


# ----------------------------------------------------------------------------- ratings


def test_course_ratings_need_a_login_and_pool_the_reviews(env: Env) -> None:
    ids = add_voices(env, codes_of(env))
    reviewed = sorted(c for c in codes_of(env) if c.startswith("CMSC"))[0]
    with env.db() as db:
        db.add(
            m.ReviewRating(
                post_id=ids["post"],
                overall=4,
                difficulty=3,
                intellectual_intensity=5,
                workload_hours=9.5,
                would_recommend=True,
            )
        )
        db.commit()
    codes = f"{reviewed},{QUANTUM},not-a-code"
    assert env.client.get("/course-ratings", params={"codes": codes}).status_code == 401
    env.signup("quiet-heron")
    resp = env.client.get("/course-ratings", params={"codes": codes})
    assert resp.status_code == 200, resp.text
    ratings = resp.json()["ratings"]
    assert set(ratings) == {reviewed, QUANTUM}
    assert ratings[reviewed]["n_reviews"] == 1 and ratings[reviewed]["overall"] == 4
    assert ratings[reviewed]["workload_hours"] == 9.5
    assert ratings[QUANTUM]["n_reviews"] == 0 and ratings[QUANTUM]["overall"] is None


def test_the_feed_endpoints_are_gone(env: Env) -> None:
    assert env.client.get("/feed").status_code == 404
    assert env.client.get("/feed/categories").status_code == 404
    assert env.client.post("/agents/feed-notes", json={"item_ids": ["course:X"]}).status_code in (
        404,
        405,
    )
