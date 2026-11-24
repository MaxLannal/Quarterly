"""The `/forum` page's API (issue #20): reviews and Commons discussions in one list, newest
first (`GET /forum/items`), and the ratings statistics and rankings (`GET /forum/stats`):
Bayesian averages with k = 5, at least 3 reviews, review counts, logged-in readers only."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from api.agents.live import CAMPUS_YEAR
from api.auth.hashing import author_ref
from api.commons.words import count_words
from api.db import models as m
from api.forum import stats
from auth_test_support import migrated_database
from test_commons_support import CommonsEnv, User, commons_env

pytestmark = pytest.mark.db

TODAY = dt.date.today()
EXTRA_COURSES = (
    ("HUMA", "11000", "Greek Thought and Literature I"),
    ("HUMA", "11100", "Greek Thought and Literature II"),
    ("CLAS", "11000", "Greek Thought and Literature I"),  # cross-listed with HUMA 11000
    ("HUMA", "12000", "Readings in World Literature I"),
)


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@dataclass
class Forum:
    c: CommonsEnv
    pages: dict[str, int]
    _n: int = 0

    def review(
        self,
        page: str,
        overall: int,
        days_ago: int = 0,
        *,
        ref: str | None = None,
        title: str | None = None,
        status: str = "visible",
        workload: float = 6.0,
        recommend: bool = True,
    ) -> int:
        self._n += 1
        with self.c.env.db() as db:
            post = m.Post(
                course_instructor_id=self.pages[page],
                kind="review",
                author_ref=ref or f"ref-{self._n}",
                title=title or f"Review {self._n}",
                body_md=f"Fake review number {self._n} of {page}.",
                term_taken="2026-SP",
                status=status,
                created_day=TODAY - dt.timedelta(days=days_ago),
            )
            db.add(post)
            db.flush()
            db.add(
                m.ReviewRating(
                    post_id=post.id,
                    overall=overall,
                    difficulty=3,
                    intellectual_intensity=3,
                    workload_hours=workload,
                    would_recommend=recommend,
                )
            )
            db.commit()
            return post.id

    def ask(self, user: User, title: str, days_ago: int = 0, **extra: Any) -> int:
        thread = user.ask(title, **extra)
        if days_ago:
            with self.c.env.db() as db:
                db.execute(
                    sa.update(m.CommonsThread)
                    .where(m.CommonsThread.id == thread["id"])
                    .values(created_day=TODAY - dt.timedelta(days=days_ago))
                )
                db.commit()
        return int(thread["id"])


def _seed(c: CommonsEnv) -> dict[str, int]:
    with c.env.db() as db:
        for subject, number, title in EXTRA_COURSES:
            db.add(
                m.Course(
                    catalog_year=CAMPUS_YEAR,
                    subject=subject,
                    number=number,
                    code=f"{subject} {number}",
                    title=title,
                )
            )
        db.flush()
        ids = {
            code: cid
            for cid, code in db.execute(
                sa.select(m.Course.id, m.Course.code).where(m.Course.catalog_year == CAMPUS_YEAR)
            )
        }
        db.add_all(
            [
                m.CrosslistGroup(group_id="greek", course_id=ids["HUMA 11000"]),
                m.CrosslistGroup(group_id="greek", course_id=ids["CLAS 11000"]),
            ]
        )
        doe = m.Instructor(slug="jane-doe", display_name="Jane Doe", department="Fake Dept")
        roe = m.Instructor(slug="rick-roe", display_name="Rick Roe")
        db.add_all([doe, roe])
        db.flush()
        pairs = {
            "cmsc141_doe": ("CMSC 14100", doe),
            "cmsc142_doe": ("CMSC 14200", doe),
            "math153_roe": ("MATH 15300", roe),
            "huma110_roe": ("HUMA 11000", roe),
            "clas110_roe": ("CLAS 11000", roe),
            "huma120_doe": ("HUMA 12000", doe),
        }
        pages = {}
        for key, (code, teacher) in pairs.items():
            page = m.CourseInstructor(course_id=ids[code], instructor_id=teacher.id, n_terms=1)
            db.add(page)
            db.flush()
            pages[key] = page.id
        for pid, name, kind, subject in (
            ("cmsc-bs", "Computer Science (BS)", "major", "CMSC"),
            ("math-bs", "Mathematics (BS)", "major", "MATH"),
            ("cmsc-minor", "Computer Science minor", "minor", "CMSC"),
        ):
            db.add(m.Program(id=pid, name=name, type=kind, degree="BS", department=subject))
            db.flush()
            rules = {
                "id": pid,
                "catalog_year": CAMPUS_YEAR,
                "rules": {
                    "kind": "select",
                    "id": "courses",
                    "count": 2,
                    "from": {"subject": subject},
                },
            }
            db.add(
                m.ProgramVersion(
                    program_id=pid,
                    catalog_year=CAMPUS_YEAR,
                    rules=rules,
                    status="published",
                    checksum="fixture",
                    sources=[],
                )
            )
        db.add_all(
            [
                m.CourseList(
                    catalog_year=CAMPUS_YEAR,
                    name="huma-11000",
                    label="HUMA 11000-11100",
                    course_ids=[ids["HUMA 11000"], ids["HUMA 11100"]],
                ),
                m.CourseList(
                    catalog_year=CAMPUS_YEAR,
                    name="huma-12000",
                    label="HUMA 12000",
                    course_ids=[ids["HUMA 12000"]],
                ),
                m.CourseList(
                    catalog_year=CAMPUS_YEAR,
                    name="core-huma-sequences",
                    label="Humanities Core sequences",
                    sublists=["huma-11000", "huma-12000"],
                ),
            ]
        )
        db.commit()
    return pages


@pytest.fixture
def f(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Forum]:
    with commons_env(db_url, monkeypatch) as c:
        yield Forum(c=c, pages=_seed(c))


def items(client: Any, **query: Any) -> dict[str, Any]:
    resp = client.get("/forum/items", params=query)
    assert resp.status_code == 200, resp.text
    out: dict[str, Any] = resp.json()
    return out


def keys(page: dict[str, Any]) -> list[str]:
    return [
        f"d{i['thread']['id']}" if i["type"] == "discussion" else f"r{i['id']}"
        for i in page["items"]
    ]


# ------------------------------------------------------------------------------------ list


def test_reviews_and_discussions_share_one_list_newest_first(f: Forum) -> None:
    reader = f.c.user()
    r_old = f.review("cmsc141_doe", 4, days_ago=2)
    t_yesterday = f.ask(reader, "Is CMSC 14100 hard?", days_ago=1, course_code="CMSC 14100")
    r_yesterday = f.review("math153_roe", 3, days_ago=1)
    r_today = f.review("cmsc142_doe", 5)
    t_today = f.ask(reader, "Which Hum sequence is best?")
    f.review("cmsc142_doe", 2, status="removed")  # never listed
    page = items(reader.client)
    # Newest day first; on one day discussions first, then the newest id.
    assert keys(page) == [
        f"d{t_today}",
        f"r{r_today}",
        f"d{t_yesterday}",
        f"r{r_yesterday}",
        f"r{r_old}",
    ]
    assert page["total"] == 5 and page["next_cursor"] is None and not page["reviews_hidden"]
    review = page["items"][1]
    assert review["course"] == {
        "code": "CMSC 14200",
        "title": "Introduction to Computer Science II",
    }
    assert review["instructor"]["slug"] == "jane-doe" and review["overall"] == 5
    assert review["handle"] == "Anonymous" and review["n_comments"] == 0
    # Pages of two: every item once, in the same order.
    seen: list[str] = []
    cursor = None
    while True:
        part = items(reader.client, limit=2, **({"cursor": cursor} if cursor else {}))
        seen += keys(part)
        cursor = part["next_cursor"]
        if cursor is None:
            break
    assert seen == keys(page)


def test_logged_out_readers_get_the_discussions_only(f: Forum) -> None:
    asker = f.c.user()
    t = f.ask(asker, "Is CMSC 14100 hard?", course_code="CMSC 14100")
    f.review("cmsc141_doe", 4)
    anon = f.c.anon()
    page = items(anon)
    assert keys(page) == [f"d{t}"] and page["reviews_hidden"] and page["total"] == 1
    only_reviews = items(anon, type="review")
    assert only_reviews["items"] == [] and only_reviews["reviews_hidden"]


def test_filters_by_type_course_instructor_and_text(f: Forum) -> None:
    reader = f.c.user()
    t_cmsc = f.ask(reader, "Is CMSC 14100 hard?", course_code="CMSC 14100", tags=["intro"])
    t_huma = f.ask(f.c.user(), "Greek Thought: worth it?", course_code="HUMA 11000")
    r_cmsc = f.review("cmsc141_doe", 4, title="Loved the labs")
    r_clas = f.review("clas110_roe", 5)
    r_math = f.review("math153_roe", 3)
    assert set(keys(items(reader.client, type="discussion"))) == {f"d{t_cmsc}", f"d{t_huma}"}
    assert set(keys(items(reader.client, type="review"))) == {
        f"r{r_cmsc}",
        f"r{r_clas}",
        f"r{r_math}",
    }
    assert set(keys(items(reader.client, course="cmsc14100"))) == {f"d{t_cmsc}", f"r{r_cmsc}"}
    # A review of a cross-listed course is found under each of its codes.
    assert f"r{r_clas}" in keys(items(reader.client, course="HUMA 11000"))
    # An instructor filter keeps reviews only: a discussion has no instructor.
    assert set(keys(items(reader.client, instructor="rick-roe"))) == {f"r{r_clas}", f"r{r_math}"}
    assert keys(items(reader.client, q="labs")) == [f"r{r_cmsc}"]
    assert set(keys(items(reader.client, subject="CMSC"))) == {f"d{t_cmsc}", f"r{r_cmsc}"}
    # Tags and "my questions" belong to the Commons: reviews are left out.
    assert keys(items(reader.client, tag="intro")) == [f"d{t_cmsc}"]
    assert keys(items(reader.client, mine="true")) == [f"d{t_cmsc}"]
    assert items(reader.client, course="not a code")["items"] == []
    assert reader.get("/forum/items", params={"cursor": "yesterday"}).status_code == 422
    assert reader.get("/forum/items", params={"type": "poll"}).status_code == 422


def test_my_review_and_my_vote_are_marked(f: Forum) -> None:
    reader = f.c.user()
    page_id = f.pages["cmsc141_doe"]
    mine = f.review("cmsc141_doe", 4, ref=author_ref(uuid.UUID(reader.account_id), page_id))
    theirs = f.review("cmsc141_doe", 2)
    vote = reader.post("/forum/votes", {"target_type": "post", "target_id": theirs, "value": 1})
    assert vote.status_code == 200, vote.text
    by_id = {i["id"]: i for i in items(reader.client, type="review")["items"]}
    assert by_id[mine]["is_mine"] and not by_id[theirs]["is_mine"]
    assert by_id[theirs]["my_vote"] == 1 and by_id[mine]["my_vote"] == 0


def test_a_discussion_carries_the_short_ai_answer(f: Forum) -> None:
    reader = f.c.user()
    t = f.ask(reader, "Is CMSC 14100 hard?", course_code="CMSC 14100")
    plain = f.ask(reader, "Is MATH 15300 hard?")
    with f.c.env.db() as db:
        db.add(
            m.CommonsReply(
                thread_id=t,
                parent_id=None,
                depth=0,
                author_ref=None,
                kind="bot",
                body_md="Yes: **CMSC 14100** moves fast. " + " ".join(["More."] * 80),
                citations=[],
                status="visible",
            )
        )
        db.commit()
    by_id = {i["thread"]["id"]: i for i in items(f.c.anon())["items"]}
    answer = by_id[t]["ai_answer_html"]
    assert 'href="/courses/CMSC%2014100"' in answer
    assert count_words(re.sub(r"<[^>]+>", " ", answer)) <= 60
    assert by_id[plain]["ai_answer_html"] is None


# ----------------------------------------------------------------------------------- stats


def _expected(ratings: list[int], prior: float) -> float:
    return round((5 * prior + sum(ratings)) / (5 + len(ratings)), 2)


def test_statistics_are_for_logged_in_students(f: Forum) -> None:
    f.review("cmsc141_doe", 4)
    assert f.c.anon().get("/forum/stats").status_code == 401


def test_rankings_use_the_bayesian_average_with_k_5_and_at_least_3_reviews(f: Forum) -> None:
    ratings = {
        "cmsc141_doe": [5, 5, 4],
        "cmsc142_doe": [5, 5],  # two reviews: never ranked
        "math153_roe": [3, 3, 3, 4],
        "huma110_roe": [4, 4],
        "clas110_roe": [5],
        "huma120_doe": [2, 3],
    }
    for page, values in ratings.items():
        for value in values:
            f.review(page, value, days_ago=10)
    f.review("math153_roe", 1, days_ago=100)  # in the year, not in the quarter
    f.review("cmsc141_doe", 1, days_ago=5, status="held")  # not visible: never counted
    reader = f.c.user()
    quarter = reader.get("/forum/stats", params={"period": "quarter"}).json()
    every = [v for values in ratings.values() for v in values]
    prior = sum(every) / len(every)
    assert quarter["n_reviews"] == 14 and quarter["prior_weight"] == 5
    assert quarter["min_reviews"] == 3 and quarter["prior_mean"] == round(prior, 2)
    assert quarter["since"] == (TODAY - dt.timedelta(days=90)).isoformat()
    assert quarter["n_courses"] == 6 and quarter["recommend_rate"] == 1.0
    top = quarter["top_courses"]
    assert [(e["id"], e["n_reviews"]) for e in top] == [("CMSC 14100", 3), ("MATH 15300", 4)]
    assert top[0]["score"] == _expected([5, 5, 4], prior) == 4.21
    assert top[0]["mean"] == 4.67 and top[0]["rank"] == 1
    assert top[0]["detail"] == "Introduction to Computer Science I"
    # Majors: the courses that can fill one of their requirements; minors are not ranked.
    majors = {r["program_id"]: r for r in quarter["majors"]}
    assert set(majors) == {"cmsc-bs", "math-bs"}
    assert [e["id"] for e in majors["cmsc-bs"]["items"]] == ["CMSC 14100"]
    assert [e["id"] for e in majors["math-bs"]["items"]] == ["MATH 15300"]
    # Humanities sequences pool their courses and the cross-listed codes (HUMA 11000 = CLAS
    # 11000); HUMA 12000 has 2 reviews.
    assert [(e["id"], e["label"], e["n_reviews"]) for e in quarter["humanities"]] == [
        ("huma-11000", "HUMA 11000-11100", 3)
    ]
    assert quarter["humanities"][0]["score"] == _expected([4, 4, 5], prior)
    assert quarter["humanities"][0]["detail"] == "Greek Thought and Literature"
    # Instructors pool their courses.
    assert [(e["id"], e["n_reviews"]) for e in quarter["instructors"]] == [
        ("jane-doe", 7),
        ("rick-roe", 7),
    ]
    assert quarter["instructors"][0]["score"] == _expected([5, 5, 4, 5, 5, 2, 3], prior)
    assert quarter["instructors"][0]["detail"] == "Fake Dept"

    year = reader.get("/forum/stats", params={"period": "year"}).json()
    prior_year = (sum(every) + 1) / (len(every) + 1)
    assert year["n_reviews"] == 15
    math = next(e for e in year["top_courses"] if e["id"] == "MATH 15300")
    assert math["n_reviews"] == 5 and math["score"] == _expected([3, 3, 3, 4, 1], prior_year)
    assert reader.get("/forum/stats", params={"period": "week"}).status_code == 422


def test_with_no_reviews_the_statistics_are_empty(f: Forum) -> None:
    out = f.c.user().get("/forum/stats").json()
    assert out["n_reviews"] == 0 and out["prior_mean"] is None
    assert out["top_courses"] == [] and out["majors"] == [] and out["instructors"] == []


def test_the_bayesian_average_pulls_few_reviews_toward_the_prior() -> None:
    assert stats.bayesian(5 * 3, 3, 3.0) == pytest.approx((5 * 3.0 + 15) / 8)
    # Three 5s do not beat thirty 4.8s when the period's average is 3.
    assert stats.bayesian(15, 3, 3.0) < stats.bayesian(4.8 * 30, 30, 3.0)
