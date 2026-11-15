"""Forum pages: one per `course_instructor` row, which the schedule pipeline creates the first
time it sees an instructor teach a course (`ensure_page`). Also the read models that pool
ratings for a page, a course (every instructor) and an instructor."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Any

import sqlalchemy as sa
from planner_core.terms import term_key
from sqlalchemy.orm import Session

from api.attributes.records import cited_ids, hidden_citations
from api.db import models as m
from api.repo.catalog import normalize_code
from api.schemas.catalog import CourseInstructorOut, InstructorSummary, RatingSummary
from api.schemas.forum import (
    CourseForumOut,
    ForumPageOut,
    ForumPageSummary,
    ForumSummaryOut,
)

RATED_FIELDS = ("overall", "difficulty", "intellectual_intensity", "pace", "grading_strictness")


class PageNotFoundError(LookupError):
    pass


def _sort_terms(terms: Collection[str]) -> list[str]:
    valid = []
    for t in set(terms):
        try:
            term_key(t)
        except ValueError:
            continue
        valid.append(t)
    return sorted(valid, key=term_key)


def crosslisted_codes(db: Session, code: str) -> list[str]:
    """`code` and every code it is cross-listed with (in any catalog year), sorted. A course
    with the same instructor has one forum page under all of them (P08-5, Richard 2026-11-14)."""
    found = {code}
    frontier = {code}
    while frontier:  # follow chains: A ~ B in one catalog year, B ~ C in another
        groups = (
            sa.select(m.CrosslistGroup.group_id)
            .join(m.Course, m.Course.id == m.CrosslistGroup.course_id)
            .where(m.Course.code.in_(frontier))
        )
        siblings = set(
            db.scalars(
                sa.select(m.Course.code)
                .join(m.CrosslistGroup, m.CrosslistGroup.course_id == m.Course.id)
                .where(m.CrosslistGroup.group_id.in_(groups))
            )
        )
        frontier = siblings - found
        found |= siblings
    return sorted(found)


def ensure_page(
    db: Session, course_id: int, instructor_id: int, term_id: str | None = None
) -> m.CourseInstructor:
    """The page for this course x instructor, created on first sight, with its term range
    widened to `term_id`. One page per course *code* and its cross-listings: a course row of
    another catalog year, or another code of the same cross-listed course, reuses the existing
    page, so reviews do not split. The caller commits."""
    course = db.get(m.Course, course_id)
    if course is None:
        raise PageNotFoundError(f"no course {course_id}")
    page = db.scalar(
        sa.select(m.CourseInstructor)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .where(
            m.Course.code.in_(crosslisted_codes(db, course.code)),
            m.CourseInstructor.instructor_id == instructor_id,
        )
        .order_by(m.CourseInstructor.id)
        .limit(1)
    )
    if page is None:
        page = m.CourseInstructor(course_id=course_id, instructor_id=instructor_id, n_terms=0)
        db.add(page)
        db.flush()
    if term_id is not None:
        if page.first_term is None or term_key(term_id) < term_key(page.first_term):
            page.first_term = term_id
        if page.last_term is None or term_key(term_id) > term_key(page.last_term):
            page.last_term = term_id
        page.n_terms = max(page.n_terms or 0, len(terms_taught(db, page) | {term_id}))
    db.flush()
    return page


def find_page(db: Session, course: str, instructor_slug: str) -> m.CourseInstructor:
    code = normalize_code(course) or course.strip().upper()
    page = db.scalar(
        sa.select(m.CourseInstructor)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .where(m.Course.code.in_(crosslisted_codes(db, code)), m.Instructor.slug == instructor_slug)
        .order_by(m.CourseInstructor.id)
        .limit(1)
    )
    if page is None:
        raise PageNotFoundError(f"No forum page for {code} with {instructor_slug}")
    return page


def get_page(db: Session, page_id: int) -> m.CourseInstructor:
    page = db.get(m.CourseInstructor, page_id)
    if page is None:
        raise PageNotFoundError(f"No forum page {page_id}")
    return page


def terms_taught(db: Session, page: m.CourseInstructor) -> set[str]:
    """Terms with a section of this course (under any of its cross-listed codes) taught by this
    instructor, plus the page's recorded first and last terms."""
    code = db.scalar(sa.select(m.Course.code).where(m.Course.id == page.course_id)) or ""
    rows = db.scalars(
        sa.select(m.Section.term_id)
        .join(m.Course, m.Course.id == m.Section.course_id)
        .where(
            m.Course.code.in_(crosslisted_codes(db, code)),
            sa.literal(page.instructor_id) == sa.func.any(m.Section.instructor_ids),
        )
        .distinct()
    )
    terms = set(rows)
    terms.update(t for t in (page.first_term, page.last_term) if t)
    return terms


def instructor_summary(row: m.Instructor) -> InstructorSummary:
    return InstructorSummary(
        slug=row.slug, display_name=row.display_name, department=row.department
    )


def _visible_reviews() -> Any:
    return (
        sa.select(
            m.Post.course_instructor_id,
            m.ReviewRating.overall,
            m.ReviewRating.difficulty,
            m.ReviewRating.intellectual_intensity,
            m.ReviewRating.workload_hours,
            m.ReviewRating.would_recommend,
            m.ReviewRating.pace,
            m.ReviewRating.grading_strictness,
        )
        .join(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
        .where(m.Post.kind == "review", m.Post.status == "visible")
    )


def ratings_by_page(db: Session, page_ids: Collection[int]) -> dict[int, RatingSummary]:
    if not page_ids:
        return {}
    reviews = _visible_reviews().where(m.Post.course_instructor_id.in_(page_ids)).subquery()
    rows = db.execute(
        sa.select(
            reviews.c.course_instructor_id,
            sa.func.count(),
            sa.func.avg(reviews.c.overall),
            sa.func.avg(reviews.c.difficulty),
            sa.func.avg(reviews.c.intellectual_intensity),
            sa.func.avg(reviews.c.workload_hours),
            sa.func.avg(sa.case((reviews.c.would_recommend, 1.0), else_=0.0)),
            sa.func.avg(reviews.c.pace),
            sa.func.avg(reviews.c.grading_strictness),
        ).group_by(reviews.c.course_instructor_id)
    )
    out = {pid: RatingSummary() for pid in page_ids}
    for pid, n, overall, difficulty, intensity, workload, recommend, pace, grading in rows:
        out[pid] = RatingSummary(
            n_reviews=n,
            overall=_round(overall),
            difficulty=_round(difficulty),
            intellectual_intensity=_round(intensity),
            workload_hours=_round(workload),
            recommend_rate=_round(recommend, 3),
            pace=_round(pace),
            grading_strictness=_round(grading),
        )
    return out


def _round(value: object, digits: int = 2) -> float | None:
    return None if value is None else round(float(str(value)), digits)


def pooled_ratings(db: Session, page_ids: Sequence[int]) -> RatingSummary:
    if not page_ids:
        return RatingSummary()
    reviews = _visible_reviews().where(m.Post.course_instructor_id.in_(page_ids)).subquery()
    n, overall, difficulty, intensity, workload, recommend, pace, grading = db.execute(
        sa.select(
            sa.func.count(),
            sa.func.avg(reviews.c.overall),
            sa.func.avg(reviews.c.difficulty),
            sa.func.avg(reviews.c.intellectual_intensity),
            sa.func.avg(reviews.c.workload_hours),
            sa.func.avg(sa.case((reviews.c.would_recommend, 1.0), else_=0.0)),
            sa.func.avg(reviews.c.pace),
            sa.func.avg(reviews.c.grading_strictness),
        )
    ).one()
    return RatingSummary(
        n_reviews=n,
        overall=_round(overall),
        difficulty=_round(difficulty),
        intellectual_intensity=_round(intensity),
        workload_hours=_round(workload),
        recommend_rate=_round(recommend, 3),
        pace=_round(pace),
        grading_strictness=_round(grading),
    )


def distribution(db: Session, page_ids: Sequence[int]) -> dict[str, list[int]]:
    """field -> counts of ratings 1..5 over the visible reviews."""
    out = {f: [0, 0, 0, 0, 0] for f in RATED_FIELDS}
    if not page_ids:
        return out
    reviews = _visible_reviews().where(m.Post.course_instructor_id.in_(page_ids)).subquery()
    for name in RATED_FIELDS:
        col = reviews.c[name]
        for value, count in db.execute(sa.select(col, sa.func.count()).group_by(col)):
            if value is not None and 1 <= value <= 5:  # pace and grading are optional
                out[name][value - 1] = count
    return out


def page_out(db: Session, page: m.CourseInstructor) -> ForumPageOut:
    course = db.get(m.Course, page.course_id)
    instructor = db.get(m.Instructor, page.instructor_id)
    assert course is not None and instructor is not None  # FKs
    ratings = ratings_by_page(db, [page.id])[page.id]
    summary_row = db.get(m.ForumSummary, page.id)
    summary = None
    # A summary citing a post that is no longer visible is not shown until the nightly job
    # rewrites it (its [n] markers would point at a removed post).
    if summary_row is not None and not hidden_citations(db, summary_row):
        citations = cited_ids(summary_row)
        summary = ForumSummaryOut(
            text=summary_row.text,
            citations=citations,
            n_posts=summary_row.n_posts,
            computed_day=summary_row.computed_at,
        )
    return ForumPageOut(
        id=page.id,
        course_code=course.code,
        also_listed_as=[c for c in crosslisted_codes(db, course.code) if c != course.code],
        course_title=course.title,
        instructor=instructor_summary(instructor),
        terms_taught=_sort_terms(terms_taught(db, page)),
        n_reviews=ratings.n_reviews,
        rating_distribution=distribution(db, [page.id]),
        ratings=ratings,
        summary=summary,
    )


def pages_of_code(db: Session, code: str) -> list[tuple[m.CourseInstructor, m.Instructor]]:
    rows = db.execute(
        sa.select(m.CourseInstructor, m.Instructor)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .where(m.Course.code.in_(crosslisted_codes(db, code)))
        .order_by(m.Instructor.display_name, m.CourseInstructor.id)
    )
    seen: set[int] = set()
    out = []
    for page, instructor in rows:
        if instructor.id in seen:  # one page per cross-listed course x instructor (ensure_page)
            continue
        seen.add(instructor.id)
        out.append((page, instructor))
    return out


def course_instructors(db: Session, code: str) -> list[CourseInstructorOut]:
    """The course page's instructor list (public: names only, P03-12)."""
    return [
        CourseInstructorOut(
            page_id=page.id,
            instructor=instructor_summary(instructor),
            first_term=page.first_term,
            last_term=page.last_term,
            n_terms=page.n_terms,
        )
        for page, instructor in pages_of_code(db, code)
    ]


def course_forum(db: Session, raw_code: str) -> CourseForumOut:
    code = normalize_code(raw_code) or raw_code.strip().upper()
    title = db.scalar(
        sa.select(m.Course.title)
        .where(m.Course.code == code)
        .order_by(m.Course.catalog_year.desc())
    )
    if title is None:
        raise PageNotFoundError(f"No course {code}")
    pages = pages_of_code(db, code)
    ids = [p.id for p, _ in pages]
    per_page = ratings_by_page(db, ids)
    return CourseForumOut(
        course_code=code,
        course_title=title,
        ratings=pooled_ratings(db, ids),
        rating_distribution=distribution(db, ids),
        pages=[
            ForumPageSummary(
                page_id=page.id,
                instructor=instructor_summary(instructor),
                terms_taught=_sort_terms(terms_taught(db, page)),
                ratings=per_page[page.id],
            )
            for page, instructor in pages
        ],
    )


def instructor_pages(db: Session, instructor_id: int) -> list[tuple[m.CourseInstructor, m.Course]]:
    rows = db.execute(
        sa.select(m.CourseInstructor, m.Course)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .where(m.CourseInstructor.instructor_id == instructor_id)
        .order_by(m.Course.code, m.CourseInstructor.id)
    )
    by_code: dict[str, tuple[m.CourseInstructor, m.Course]] = {}
    for page, course in rows:
        by_code.setdefault(course.code, (page, course))
    return list(by_code.values())
