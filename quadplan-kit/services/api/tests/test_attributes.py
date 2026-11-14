"""Prompt 11: forum -> course attributes and "What students say" (FakeLLM only)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.attributes import a3, job
from api.attributes.aggregate import (
    K_DEPARTMENT,
    K_ESTIMATE,
    Prior,
    Rating,
    department_prior,
    posterior,
    rating_weight,
)
from api.attributes.job import run_nightly
from api.db import models as m
from api.forum import pages
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from llm_gateway.api import FakeLLM, LLMUnavailableError, UnavailableLLM
from sqlalchemy.orm import Session

TODAY = dt.date(2026, 11, 14)
EMPTY = {
    "workload_mentions": [],
    "difficulty_cues": [],
    "exam_style": [],
    "prerequisite_advice": [],
}
GUESS = {"workload_hours": 8, "difficulty": 2, "reason": "10000-level, weekly problem sets."}


# ------------------------------------------------------------------------------ the formula


def test_formula_matches_hand_computed_cases() -> None:
    est = posterior(
        "difficulty",
        [Rating(5, 1), Rating(4, 1), Rating(2, 0.5)],
        Prior(3.0, K_DEPARTMENT, "department"),
    )
    assert est is not None
    assert est.value == pytest.approx((5 * 3 + 5 + 4 + 0.5 * 2) / (5 + 2.5), abs=1e-3)  # 3.333
    assert est.n == 3 and est.ci_low < est.value < est.ci_high
    plain = posterior("workload_hours", [Rating(10, 1), Rating(20, 1)], None)
    assert plain is not None and plain.value == 15
    estimate = posterior("workload_hours", [Rating(12, 1)], Prior(8, K_ESTIMATE, "estimate"))
    assert estimate is not None and estimate.value == pytest.approx((2 * 8 + 12) / 3, abs=1e-3)
    assert posterior("difficulty", [], None) is None
    clamped = posterior("recommend_rate", [Rating(1, 1)], None)
    assert clamped is not None and 0 <= clamped.ci_low <= clamped.value <= clamped.ci_high <= 1


def test_weights_and_department_prior() -> None:
    assert rating_weight("review", TODAY - dt.timedelta(days=30), TODAY) == 1.0
    assert rating_weight("text", TODAY, TODAY) == 0.5
    assert rating_weight("review", TODAY - dt.timedelta(days=5 * 365), TODAY) == 0.5
    assert department_prior([Rating(3, 1), Rating(4, 1)]) is None
    prior = department_prior([Rating(3, 1), Rating(4, 1), Rating(5, 0.5)])
    assert prior is not None and prior.weight == K_DEPARTMENT
    assert prior.mean == pytest.approx((3 + 4 + 2.5) / 2.5)


def test_extraction_keeps_only_quoted_facts() -> None:
    post = "Expect about 12 hours a week. The midterm was brutal but fair."
    raw = a3.Extraction.model_validate(
        {
            "workload_mentions": [
                {"hours": 12, "quote": "about 12 hours a week"},
                {"hours": 40, "quote": "The midterm was brutal"},  # number not in its quote
                {"hours": 5, "quote": "only 5 hours"},  # quote not in the post
            ],
            "difficulty_cues": [{"level": "hard", "quote": "the midterm was BRUTAL"}],
            "exam_style": [{"text": "Hard but fair midterm", "quote": "brutal but fair"}],
            "prerequisite_advice": [{"text": "Take X first", "quote": "not in the post"}],
        }
    )
    kept = a3.checked_extraction(raw, post)
    assert [w.hours for w in kept.workload_mentions] == [12]
    assert len(kept.difficulty_cues) == 1 and len(kept.exam_style) == 1
    assert kept.prerequisite_advice == []


@pytest.mark.parametrize(
    ("text", "citations", "problem"),
    [
        ("Heavy problem sets [1].", [999], "not given"),
        ("Too long [1]. " + "word " * 120, [1], "words"),
        ("No markers at all.", [1], "marker"),
        ("Points at nothing [3].", [1], "marker"),
        ("Cites nothing.", [], "cites no post"),
    ],
)
def test_summary_rules(text: str, citations: list[int], problem: str) -> None:
    with pytest.raises(a3.SummaryRejectedError, match=problem):
        a3.checked_summary(a3.Summary(text=text, citations=citations), {1, 2})


# ----------------------------------------------------------------------------- the job


@pytest.fixture
def db(migrated_db_url: str) -> Iterator[Session]:
    engine = sa.create_engine(migrated_db_url)
    with Session(engine) as session:
        upsert_bundle(session, load_bundle(FIXTURES / "seed" / "2099-00"))
        yield session
    engine.dispose()


def make_page(db: Session, code: str = "TEST 10000", slug: str = "demo-a") -> m.CourseInstructor:
    course = db.scalar(sa.select(m.Course).where(m.Course.code == code))
    assert course is not None
    instructor = m.Instructor(slug=slug, display_name="Demo Instructor (fake)")
    db.add(instructor)
    db.flush()
    page = m.CourseInstructor(course_id=course.id, instructor_id=instructor.id)
    db.add(page)
    db.flush()
    return page


def review(
    db: Session,
    page: m.CourseInstructor,
    *,
    workload: float,
    difficulty: int = 3,
    day: dt.date = TODAY,
    body: str = "Solid course.",
) -> m.Post:
    post = m.Post(
        course_instructor_id=page.id,
        kind="review",
        author_ref=uuid.uuid4().hex,
        body_md=body,
        status="visible",
        created_day=day,
    )
    db.add(post)
    db.flush()
    db.add(
        m.ReviewRating(
            post_id=post.id,
            overall=4,
            difficulty=difficulty,
            intellectual_intensity=3,
            workload_hours=workload,
            would_recommend=True,
        )
    )
    db.flush()
    return post


def value(db: Session, subject_type: str, subject_id: str, key: str) -> m.AttributeValue | None:
    return db.scalar(
        sa.select(m.AttributeValue).where(
            m.AttributeValue.subject_type == subject_type,
            m.AttributeValue.subject_id == subject_id,
            m.AttributeValue.key == key,
        )
    )


def fake(**script: list[Any]) -> FakeLLM:
    return FakeLLM(script={k: list(v) for k, v in script.items()})


@pytest.mark.db
def test_below_three_reviews_the_course_shows_its_estimate(db: Session) -> None:
    page = make_page(db)
    review(db, page, workload=20, difficulty=5)
    review(db, page, workload=22, difficulty=4)
    llm = fake(a3_cold_start_estimate=[GUESS])
    stats = run_nightly(db, llm, TODAY)
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.method == "prior" and row.n == 0 and row.value == 8
    assert row.evidence["estimate"] == 8
    page_row = value(db, "course_instructor", str(page.id), "difficulty")
    assert page_row is not None and page_row.value == 2 and page_row.method == "prior"
    assert stats.cold_start == 1 and stats.extracted == 0  # reviews are not text-extracted
    assert db.get(m.ForumSummary, page.id) is None  # no summary answer: nothing published


def discussion(db: Session, page: m.CourseInstructor, body: str) -> m.Post:
    post = m.Post(
        course_instructor_id=page.id,
        kind="discussion",
        author_ref=uuid.uuid4().hex,
        title="Workload?",
        body_md=body,
        status="visible",
        created_day=TODAY,
    )
    db.add(post)
    db.flush()
    return post


def mentions(*pairs: tuple[float, str]) -> dict[str, Any]:
    return {**EMPTY, "workload_mentions": [{"hours": h, "quote": q} for h, q in pairs]}


@pytest.mark.db
def test_two_reviews_and_a_discussion_publish_a_blend_with_a_text_value(db: Session) -> None:
    page = make_page(db)
    review(db, page, workload=10, body="Expect about 25 hours a week.")  # never text-extracted
    review(db, page, workload=12)
    discussion(db, page, "About 30 hours in project weeks, some weeks 20 hours.")
    found = mentions(
        (30, "About 30 hours in project weeks"),
        (20, "some weeks 20 hours"),
        (40, "About"),  # number missing from the quote
    )
    llm = fake(a3_cold_start_estimate=[GUESS], a3_forum_extraction=[found])
    stats = run_nightly(db, llm, TODAY)
    assert stats.extracted == 1
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.method == "blend" and row.n == 3  # three posts
    # The discussion counts once, as the mean of its two accepted mentions, at half weight.
    expected = (K_ESTIMATE * 8 + 10 + 12 + 0.5 * 25) / (K_ESTIMATE + 2.5)
    assert row.value == pytest.approx(expected, abs=1e-3)
    assert row.evidence["from_text"] == 1 and row.evidence["prior"]["kind"] == "estimate"
    assert row.ci_low < row.value < row.ci_high


@pytest.mark.db
def test_one_post_never_reaches_three_ratings(db: Session) -> None:
    page = make_page(db)
    discussion(db, page, "Week 1: 10 hours. Week 2: 12 hours. Week 3: 14 hours.")
    found = mentions((10, "10 hours"), (12, "12 hours"), (14, "14 hours"))
    run_nightly(db, fake(a3_cold_start_estimate=[GUESS], a3_forum_extraction=[found]), TODAY)
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.method == "prior" and row.value == 8


@pytest.mark.db
def test_an_edited_post_is_extracted_again_and_old_values_drop(db: Session) -> None:
    page = make_page(db)
    review(db, page, workload=10)
    review(db, page, workload=12)
    post = discussion(db, page, "Easily 40 hours a week.")
    llm = fake(a3_cold_start_estimate=[GUESS], a3_forum_extraction=[mentions((40, "40 hours"))])
    run_nightly(db, llm, TODAY)
    assert value(db, "course", "TEST 10000", "workload_hours").n == 3  # type: ignore[union-attr]

    post.body_md = "I take that back, it was fine."  # edited: the 40 is gone
    db.flush()
    run_nightly(db, fake(a3_forum_extraction=[EMPTY]), TODAY)
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.method == "prior"  # back to two posts: the estimate shows
    llm = fake()
    run_nightly(db, llm, TODAY)  # nothing changed: not extracted a third time
    assert not [c for c in llm.calls if c["task"] == "a3_forum_extraction"]
    runs = db.scalars(sa.select(m.ExtractionRun)).all()
    assert len(runs) == 1 and runs[0].output is not None
    assert runs[0].output["workload_mentions"] == []  # the old quote is gone


@pytest.mark.db
def test_page_prior_is_the_department_average(db: Session) -> None:
    page = make_page(db)
    other = make_page(db, code="TEST 10100", slug="demo-b")
    for w in (20, 22, 24):
        review(db, other, workload=w)
    for w in (6, 8, 10):
        review(db, page, workload=w)
    run_nightly(db, UnavailableLLM(), TODAY)
    row = value(db, "course_instructor", str(page.id), "workload_hours")
    assert row is not None and row.evidence["prior"] == {
        "kind": "department",
        "mean": 22.0,
        "weight": K_DEPARTMENT,
    }


def test_escaped_quotes_still_match_the_post() -> None:
    raw = a3.Extraction.model_validate(mentions((5, "&lt;5 hrs most weeks")))
    kept = a3.checked_extraction(raw, "Honestly <5 hrs most weeks.")
    assert [w.hours for w in kept.workload_mentions] == [5]


@pytest.mark.db
def test_old_reviews_weigh_half(db: Session) -> None:
    page = make_page(db)
    review(db, page, workload=10)
    review(db, page, workload=10)
    review(db, page, workload=40, day=TODAY - dt.timedelta(days=5 * 365))
    run_nightly(db, UnavailableLLM(), TODAY)
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.method == "forum"
    assert row.value == pytest.approx((10 + 10 + 0.5 * 40) / 2.5, abs=1e-3)


@pytest.mark.db
def test_without_an_llm_only_structured_ratings_count(db: Session) -> None:
    page = make_page(db)
    for workload in (6, 8, 10):
        review(db, page, workload=workload)
    stats = run_nightly(db, UnavailableLLM(), TODAY)
    assert not stats.llm_available and stats.summaries == 0 and stats.extracted == 0
    row = value(db, "course", "TEST 10000", "workload_hours")
    assert row is not None and row.value == 8 and row.method == "forum"


@pytest.mark.db
def test_summaries_are_checked_and_moderated_before_publishing(db: Session) -> None:
    page = make_page(db)
    posts = [review(db, page, workload=w) for w in (8, 9, 10)]
    ids = [p.id for p in posts]
    good = {
        "text": "Steady weekly work [1]; most found it fair [2].",
        "citations": [ids[0], ids[1]],
    }
    extraction = [EMPTY, EMPTY, EMPTY]

    # 1. A citation to a post the model was not given: rejected.
    llm = fake(
        a3_cold_start_estimate=[GUESS],
        a3_forum_extraction=extraction,
        a3_forum_summary=[{"text": "Heavy [1].", "citations": [ids[0] + 999]}],
    )
    stats = run_nightly(db, llm, TODAY)
    assert db.get(m.ForumSummary, page.id) is None and any("not given" in r for r in stats.rejected)

    # 2. Moderation cannot answer: not published.
    llm = fake(a3_forum_summary=[good], a4_moderation=[LLMUnavailableError("down")])
    run_nightly(db, llm, TODAY)
    assert db.get(m.ForumSummary, page.id) is None

    # 3. Moderation flags it: not published.
    llm = fake(a3_forum_summary=[good], a4_moderation=[{"label": "personal_attack"}])
    run_nightly(db, llm, TODAY)
    assert db.get(m.ForumSummary, page.id) is None

    # 4. Clean summary, moderation says ok: published with its citations.
    llm = fake(a3_forum_summary=[good], a4_moderation=[{"label": "ok"}])
    stats = run_nightly(db, llm, TODAY)
    row = db.get(m.ForumSummary, page.id)
    assert row is not None and stats.summaries == 1
    assert [c["post_id"] for c in row.citations] == ids[:2] and row.n_posts == 3
    assert row.computed_at == TODAY and row.model == "a3_forum_summary"
    sent = next(c for c in llm.calls if c["task"] == "a3_forum_summary")["messages"][0].content
    assert sent.count("<untrusted_source") == 3

    # 5. Not rebuilt until 3 new posts or 30 days.
    llm = fake()
    run_nightly(db, llm, TODAY + dt.timedelta(days=5))
    assert not [c for c in llm.calls if c["task"] == "a3_forum_summary"]

    # 6. A cited post is removed: the summary is hidden at once and rewritten that night.
    posts[0].status = "removed"
    db.flush()
    row = db.get(m.ForumSummary, page.id)
    assert row is not None and job.hidden_citations(db, row)
    assert pages.page_out(db, page).summary is None
    rewritten = {"text": "Fair course [1].", "citations": [ids[1]]}
    llm = fake(a3_forum_summary=[rewritten], a4_moderation=[{"label": "ok"}])
    run_nightly(db, llm, TODAY + dt.timedelta(days=6))
    out = pages.page_out(db, page).summary
    assert out is not None and out.citations == [ids[1]]
