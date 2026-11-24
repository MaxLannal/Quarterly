"""Statistics and rankings on `/forum` (issue #20, `GET /forum/stats`), for logged-in readers.

Only structured ratings count (`review_rating.overall`, 1-5) from visible reviews posted in the
period: the last 91 days ("quarter", about one quarter and its break) or the last 365 days
("year"), counted back from today and including it.

Each subject (a course with every instructor pooled, a Humanities sequence, an instructor) is
scored with the Bayesian average of docs/SPEC.md "Forum -> course attributes":

    score = (k * m + sum of ratings) / (k + n)

with prior weight k = 5 and prior mean m = the average overall rating of every review in the
period (one prior for all subjects, so scores from different departments compare). Structured
ratings have weight 1, and no rating in a period of at most a year is old enough to decay. As
SPEC says for every forum-derived value, a subject needs at least 3 reviews to be shown; each
ranked line carries its review count.

Rankings: the top courses; for each major, its best-rated courses (a course belongs to a major
when it can fill one of the major's requirements, the "counts toward" rule); the Humanities
sequences (the sublists of the Core list `core-huma-sequences`, each sequence pooling the
reviews of its courses and their cross-listed codes); and the instructors.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import sqlalchemy as sa
from planner_core.models import ProgramRules
from sqlalchemy.orm import Session

from api.agents.live import CAMPUS_YEAR
from api.db import models as m
from api.forum.pages import crosslisted_codes
from api.repo import catalog as catalog_repo
from api.schemas.board import ForumStats, MajorRanking, Period, RankedEntry

#: k: the prior weight of the Bayesian average (docs/SPEC.md).
PRIOR_WEIGHT = 5
#: Forum-derived values are shown only from this many reviews (docs/SPEC.md).
MIN_REVIEWS = 3
PERIOD_DAYS: dict[str, int] = {"quarter": 91, "year": 365}
TOP_COURSES = 10
PER_MAJOR = 5
TOP_INSTRUCTORS = 10
HUMANITIES_LIST = "core-huma-sequences"
_PART_NUMBER = re.compile(r"\s*(?:\b(?:I|1)|\(I\)|:\s*Part\s+(?:I|1|One))\s*$", re.IGNORECASE)


def bayesian(total: float, n: int, prior_mean: float, k: int = PRIOR_WEIGHT) -> float:
    return (k * prior_mean + total) / (k + n)


@dataclass
class _Pool:
    ratings: list[int] = field(default_factory=list)

    def add(self, overall: int) -> None:
        self.ratings.append(overall)

    @property
    def n(self) -> int:
        return len(self.ratings)


@dataclass(frozen=True)
class _Review:
    course_code: str
    course_title: str
    instructor_id: int
    overall: int
    would_recommend: bool
    workload_hours: float


def _reviews(db: Session, since: dt.date) -> list[_Review]:
    p = m.Post
    rows = db.execute(
        sa.select(
            m.Course.code,
            m.Course.title,
            m.CourseInstructor.instructor_id,
            m.ReviewRating.overall,
            m.ReviewRating.would_recommend,
            m.ReviewRating.workload_hours,
        )
        .select_from(p)
        .join(m.ReviewRating, m.ReviewRating.post_id == p.id)
        .join(m.CourseInstructor, m.CourseInstructor.id == p.course_instructor_id)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .where(p.kind == "review", p.status == "visible", p.created_day >= since)
    ).all()
    return [_Review(*row) for row in rows]


def _ranked(
    pools: dict[str, _Pool],
    prior_mean: float,
    labels: dict[str, tuple[str, str | None]],
    limit: int | None,
) -> list[RankedEntry]:
    """Subjects with at least MIN_REVIEWS reviews, best score first (ties: more reviews, then
    the label)."""
    scored = [
        (bayesian(sum(pool.ratings), pool.n, prior_mean), pool, ident)
        for ident, pool in pools.items()
        if pool.n >= MIN_REVIEWS
    ]
    scored.sort(key=lambda x: (-x[0], -x[1].n, labels[x[2]][0]))
    out = []
    for i, (score, pool, ident) in enumerate(scored[:limit] if limit else scored, start=1):
        label, detail = labels[ident]
        out.append(
            RankedEntry(
                rank=i,
                id=ident,
                label=label,
                detail=detail,
                score=round(score, 2),
                mean=round(sum(pool.ratings) / pool.n, 2),
                n_reviews=pool.n,
            )
        )
    return out


def _majors(
    db: Session,
    rated: Iterable[str],
    by_course: dict[str, _Pool],
    prior_mean: float,
    labels: dict[str, tuple[str, str | None]],
    statuses: Sequence[str],
) -> list[MajorRanking]:
    programs = catalog_repo._program_rows(db, CAMPUS_YEAR, statuses, program_type="major")
    if not programs:
        return []
    codes = sorted(rated)
    matcher = (
        catalog_repo.SelectorMatcher(catalog_repo.load_catalog(db, CAMPUS_YEAR)) if codes else None
    )
    out = []
    for program, version in programs:
        members: set[str] = set()
        if matcher is not None:
            targets = [
                node
                for _, node in catalog_repo.fill_targets(ProgramRules.model_validate(version.rules))
            ]
            members = {c for c in codes if any(matcher.fills(c, node) for node in targets)}
        pools = {c: by_course[c] for c in members}
        out.append(
            MajorRanking(
                program_id=program.id,
                name=program.name,
                items=_ranked(pools, prior_mean, labels, PER_MAJOR),
            )
        )
    return out


def _sequence_title(title: str | None) -> str | None:
    """ "Greek Thought and Literature I" -> "Greek Thought and Literature"."""
    if not title:
        return None
    return _PART_NUMBER.sub("", title).strip() or title


def _humanities(db: Session, reviews: list[_Review], prior_mean: float) -> list[RankedEntry]:
    lists = {
        row.name: row
        for row in db.scalars(
            sa.select(m.CourseList).where(m.CourseList.catalog_year == CAMPUS_YEAR)
        )
    }
    parent = lists.get(HUMANITIES_LIST)
    if parent is None or not reviews:
        return []
    ids = {cid for name in parent.sublists if name in lists for cid in lists[name].course_ids}
    rows = db.execute(
        sa.select(m.Course.id, m.Course.code, m.Course.title).where(m.Course.id.in_(ids))
    )
    code_of = {cid: (code, title) for cid, code, title in rows}
    pools: dict[str, _Pool] = {}
    labels: dict[str, tuple[str, str | None]] = {}
    for name in parent.sublists:
        seq = lists.get(name)
        if seq is None:
            continue
        codes = [code_of[c][0] for c in seq.course_ids if c in code_of]
        group: set[str] = set()
        for code in codes:
            group.update(crosslisted_codes(db, code))
        pool = _Pool()
        for review in reviews:
            if review.course_code in group:
                pool.add(review.overall)
        pools[name] = pool
        first = (
            code_of[seq.course_ids[0]][1]
            if seq.course_ids and seq.course_ids[0] in code_of
            else None
        )
        labels[name] = (seq.label or name, _sequence_title(first))
    return _ranked(pools, prior_mean, labels, None)


def forum_stats(
    db: Session,
    period: Period,
    *,
    statuses: Sequence[str] = catalog_repo.PUBLISHED,
    today: dt.date | None = None,
) -> ForumStats:
    since = _since(period, today)
    reviews = _reviews(db, since)
    n = len(reviews)
    prior = sum(r.overall for r in reviews) / n if n else None
    by_course: dict[str, _Pool] = defaultdict(_Pool)
    by_instructor: dict[str, _Pool] = defaultdict(_Pool)
    course_labels: dict[str, tuple[str, str | None]] = {}
    for r in reviews:
        by_course[r.course_code].add(r.overall)
        course_labels[r.course_code] = (r.course_code, r.course_title)
    ids = {r.instructor_id for r in reviews}
    stats = ForumStats(
        period=period,
        since=since,
        prior_weight=PRIOR_WEIGHT,
        min_reviews=MIN_REVIEWS,
        prior_mean=round(prior, 2) if prior is not None else None,
        n_reviews=n,
        n_courses=len(by_course),
        recommend_rate=round(sum(r.would_recommend for r in reviews) / n, 3) if n else None,
        workload_hours=round(sum(r.workload_hours for r in reviews) / n, 1) if n else None,
    )
    if prior is None:
        return stats
    teachers = {
        row.id: row for row in db.scalars(sa.select(m.Instructor).where(m.Instructor.id.in_(ids)))
    }
    instructor_labels: dict[str, tuple[str, str | None]] = {}
    for r in reviews:
        teacher = teachers[r.instructor_id]
        by_instructor[teacher.slug].add(r.overall)
        instructor_labels[teacher.slug] = (teacher.display_name, teacher.department)
    rated = [code for code, pool in by_course.items() if pool.n >= MIN_REVIEWS]
    stats.top_courses = _ranked(by_course, prior, course_labels, TOP_COURSES)
    stats.majors = _majors(db, rated, by_course, prior, course_labels, statuses)
    stats.humanities = _humanities(db, reviews, prior)
    stats.instructors = _ranked(by_instructor, prior, instructor_labels, TOP_INSTRUCTORS)
    return stats


# The statistics are the same for every reader: keep them for PAGE_CACHE_TTL_S seconds per
# process (off when 0, as in tests), so a busy page does not reload the catalog on every read.
_cache: dict[tuple[str, tuple[str, ...]], tuple[float, ForumStats]] = {}


def cached_stats(db: Session, period: Period, *, statuses: Sequence[str]) -> ForumStats:
    from api.config import get_settings

    ttl = get_settings().page_cache_ttl_s
    key = (period, tuple(statuses))
    now = time.monotonic()
    hit = _cache.get(key) if ttl > 0 else None
    if hit is not None and now - hit[0] < ttl and hit[1].since == _since(period):
        return hit[1]
    out = forum_stats(db, period, statuses=statuses)
    if ttl > 0:
        _cache[key] = (now, out)
    return out


def _since(period: Period, today: dt.date | None = None) -> dt.date:
    return (today or dt.date.today()) - dt.timedelta(days=PERIOD_DAYS[period] - 1)
