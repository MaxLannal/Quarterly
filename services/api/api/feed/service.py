"""The Catalog page's browse rows (`GET /catalog/browse`, issue #19): course spotlights, what
students say, and newly released courses.

These rows replace the Feed page (D1: the course spotlights and the student quotes move into the
Catalog; the floating words, the ticker, the focus chips, the book shelf and the AI headline went).
Everything here is deterministic: the same viewer on the same day gets the same rows, and every
reason line is written by this code, never by a model.

- **Course spotlights**, logged in: courses whose title or description match the student's
  research areas and intended programs (whole words; a match in the title counts double; the
  student record has no other free text, Issue #14 D2), plus followed courses; then the
  best of each category. Logged out (or nothing to go on): a curated "best of UChicago" mix
  across categories (Core courses, approachable levels, rich descriptions), rotated daily.
- **What students say**: the newest Commons replies about a course (public), and for a
  logged-in reader also forum reviews and discussions (the forum needs a login to read).
- **Newly released courses**: `api.feed.new_courses`.

Courses are spread so no two in a row share a category when there is a choice.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db import models as m
from api.feed import text as ftext
from api.feed.categories import BY_KEY, CATEGORIES, Category, category_for, motif_for
from api.feed.pool import Pool, PoolCourse, get_pool, jitter, stable
from api.repo import catalog as catalog_repo
from api.schemas.browse import (
    CommentItem,
    CourseItem,
    CourseRef,
    CourseStats,
    FeedCategoryRef,
    Illustration,
)

#: How many cards each row holds.
SPOTLIGHTS = 12
QUOTES = 10
#: How many courses the spotlight ranking looks at before it spreads the categories.
STREAM_COURSES = 60
SNIPPET = 240
EXCERPT = 300

#: The curated mix's order of categories (sciences and humanities alternate).
CURATED = (
    "core", "physical", "literature", "computing", "philosophy", "life", "economics", "arts",
    "math", "history", "society", "mind", "area", "environment", "languages", "more",
)  # fmt: skip

#: The student record's free-text answers the feed matches against (Issue #14 D2: only the
#: research areas are free text; the intended programs are added below).
_INTEREST_SOURCES: tuple[tuple[str, float, str], ...] = (
    ("research_areas", 0.9, "Near your research interest: {}"),
)
_PROGRAM_REASON = "Fits your {} plans"
MAX_INTERESTS = 16
#: Courses one interest can bring into a day's row.
PER_INTEREST = 40


# ----------------------------------------------------------------------------- the viewer


@dataclass(frozen=True)
class Interest:
    text: str
    weight: float
    #: The reason for a course that names the whole interest ("Because you're into ...").
    reason: str
    #: The reason for a course that has all its words but not the phrase.
    near_reason: str
    phrase: str
    pattern: re.Pattern[str]
    words: tuple[tuple[str, re.Pattern[str]], ...]

    @classmethod
    def make(cls, text: str, weight: float, template: str) -> Interest | None:
        clean = ftext.squash(text)[:60].strip(" .,;:")
        if len(clean) < 2:
            return None
        significant = list(dict.fromkeys(ftext.significant_words(clean)))
        words = (
            tuple((w, ftext.term_pattern(w)) for w in significant) if len(significant) > 1 else ()
        )
        return cls(
            text=clean,
            weight=weight,
            reason=_cap(template.format(clean), 80),
            near_reason=_cap(f"Close to your interest in {clean}", 80),
            phrase=clean.lower(),
            pattern=ftext.term_pattern(clean.lower()),
            words=words,
        )

    def match(self, c: PoolCourse) -> tuple[float, bool]:
        """(score, whole phrase?): 6 for the phrase in the title, 3 in the description; for an
        interest of several words not there as a phrase, 1.5 when every word is there (2 when
        one is in the title), else nothing."""
        if self.phrase in c.low_text:
            if self.phrase in c.low_title and self.pattern.search(c.low_title):
                return 6.0 * self.weight, True
            if self.pattern.search(c.low_text):
                return 3.0 * self.weight, True
        if not self.words:
            return 0.0, False
        in_title = False
        for word, pattern in self.words:
            if word not in c.low_text or not pattern.search(c.low_text):
                return 0.0, False
            in_title = in_title or (word in c.low_title and bool(pattern.search(c.low_title)))
        return (2.0 if in_title else 1.5) * self.weight, False

    def score(self, c: PoolCourse) -> float:
        return self.match(c)[0]


@dataclass
class Viewer:
    account_id: uuid.UUID | None = None
    interests: list[Interest] = field(default_factory=list)
    followed_courses: list[str] = field(default_factory=list)
    followed_threads: list[int] = field(default_factory=list)
    intended_programs: list[str] = field(default_factory=list)

    @property
    def logged_in(self) -> bool:
        return self.account_id is not None


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else ftext.excerpt(text, limit)


def _strings(values: Iterable[object] | None) -> list[str]:
    return [str(v) for v in (values or []) if isinstance(v, str) and v.strip()]


def load_viewer(db: Session, account_id: uuid.UUID | None) -> Viewer:
    """What the feed knows about the student: their profile, read directly."""
    if account_id is None:
        return Viewer()
    viewer = Viewer(account_id=account_id)
    profile = db.get(m.StudentProfile, account_id)
    if profile is not None:
        seen: set[str] = set()
        for attr, weight, template in _INTEREST_SOURCES:
            for raw in _strings(getattr(profile, attr, None)):
                interest = Interest.make(raw, weight, template)
                if interest is not None and interest.phrase not in seen:
                    seen.add(interest.phrase)
                    viewer.interests.append(interest)
        follows = profile.follows if isinstance(profile.follows, dict) else {}
        viewer.followed_courses = [
            c
            for c in (catalog_repo.normalize_code(x) for x in _strings(follows.get("courses")))
            if c
        ]
        viewer.followed_threads = [
            int(t)
            for t in follows.get("threads", []) or []
            if isinstance(t, int | str) and str(t).isdigit()
        ]
        viewer.intended_programs = _strings(profile.intended_programs)
        if viewer.intended_programs:
            rows = db.execute(
                sa.select(m.Program.id, m.Program.name, m.Program.department).where(
                    m.Program.id.in_(viewer.intended_programs)
                )
            ).all()
            for row in rows:
                subject = row.department or row.name
                interest = Interest.make(
                    str(subject), 0.6, _PROGRAM_REASON.format(_cap(str(row.name), 40))
                )
                if interest is not None and interest.phrase not in seen:
                    seen.add(interest.phrase)
                    viewer.interests.append(interest)
        viewer.interests = viewer.interests[:MAX_INTERESTS]
    return viewer


# ----------------------------------------------------------------------------- picks


@dataclass(frozen=True)
class Pick:
    course: PoolCourse
    reason: str


@dataclass
class Ctx:
    db: Session
    pool: Pool
    viewer: Viewer
    seed: str


def _ref(cat: Category) -> FeedCategoryRef:
    return FeedCategoryRef(key=cat.key, label=cat.label, motif=cat.motif)


def _best_of(ctx: Ctx, categories: Sequence[str], *, exclude: set[str], limit: int) -> list[Pick]:
    """The curated mix: each category's best courses (quality plus a daily rotation), taken in
    turn from the categories."""
    order = [k for k in CURATED if k in categories]
    if not order:
        return []
    start = stable(ctx.seed, "start") % len(order)
    order = order[start:] + order[:start]
    queues: dict[str, list[PoolCourse]] = {}
    for key in order:
        rows = [c for c in ctx.pool.by_category.get(key, []) if c.code not in exclude]
        rows.sort(key=lambda c: -(c.quality + 2.2 * jitter(ctx.seed, "best", c.code)))
        queues[key] = rows[:60]
    picks: list[Pick] = []
    while len(picks) < limit and any(queues.values()):
        for key in order:
            if queues[key] and len(picks) < limit:
                course = queues[key].pop(0)
                picks.append(Pick(course, _curated_reason(course)))
    return picks


def _curated_reason(course: PoolCourse) -> str:
    label = BY_KEY[course.category].label
    if course.core_tags:
        if course.category == "core":
            return "In the Core, the College's shared conversation"
        return f"A Core course in {label}"
    return f"Best of UChicago: {label}"


def _for_you(ctx: Ctx) -> list[Pick]:
    """Matches for the student's interests (each interest in turn, so one broad interest
    cannot fill the page), with one curated course after every four; then the curated mix."""
    viewer = ctx.viewer
    categories = [c.key for c in CATEGORIES]
    allowed = set(categories)
    groups: dict[str, list[tuple[float, Pick]]] = {}
    if viewer.interests or viewer.followed_courses:
        for course in ctx.pool.courses:
            if course.category not in allowed:
                continue
            best, best_score, total, whole = None, 0.0, 0.0, False
            for interest in viewer.interests:
                s, exact = interest.match(course)
                total += s
                if s > best_score:
                    best, best_score, whole = interest, s, exact
            reason = "" if best is None else best.reason if whole else best.near_reason
            group = best.phrase if best is not None else ""
            if course.code in viewer.followed_courses:
                total += 3.0
                reason = reason or "You follow this course"
                group = group or "\x00follow"
            if total <= 0:
                continue
            rank = total + 0.3 * course.quality + 0.8 * jitter(ctx.seed, "fy", course.code)
            groups.setdefault(group, []).append((rank, Pick(course, reason)))
    for rows in groups.values():
        rows.sort(key=lambda t: -t[0])
    order = sorted(groups, key=lambda k: -groups[k][0][0])
    queues = {k: [p for _, p in groups[k][:PER_INTEREST]] for k in order}
    cap = STREAM_COURSES * 2 // 3
    matched: list[Pick] = []
    while len(matched) < cap and any(queues.values()):
        for key in order:
            if queues[key] and len(matched) < cap:
                matched.append(queues[key].pop(0))
    taken = {p.course.code for p in matched}
    fill = _best_of(ctx, categories, exclude=taken, limit=STREAM_COURSES - len(matched))
    picks: list[Pick] = []
    used = 0
    for i, pick in enumerate(matched, start=1):
        picks.append(pick)
        if i % 4 == 0 and used < len(fill):
            picks.append(fill[used])
            used += 1
    return picks + fill[used:]


def _spread(picks: list[Pick], window: int = 10) -> list[Pick]:
    """No two courses of one category in a row when a later one (within `window`) differs."""
    rest = list(picks)
    out: list[Pick] = []
    while rest:
        last = out[-1].course.category if out else None
        index = next(
            (i for i, p in enumerate(rest[:window]) if p.course.category != last),
            0,
        )
        out.append(rest.pop(index))
    return out


# ----------------------------------------------------------------------------- what students say


def _course_ref(code: str, title: str) -> CourseRef:
    return CourseRef(code=code, title=ftext.squash(title))


def _thread_href(thread_id: int) -> str:
    return f"/forum/t/{thread_id}"


def _commons_comments(ctx: Ctx, limit: int = 40) -> list[CommentItem]:
    reply, thread, course = m.CommonsReply, m.CommonsThread, m.Course
    filters = [
        reply.status == "visible",
        reply.kind == "human",
        thread.status == "visible",
        thread.course_id.is_not(None),
    ]
    rows = ctx.db.execute(
        sa.select(reply, thread.id, course.code, course.title, course.subject)
        .join(thread, thread.id == reply.thread_id)
        .join(course, course.id == thread.course_id)
        .where(*filters)
        .order_by(reply.id.desc())
        .limit(limit)
    ).all()
    handles = _commons_handles(ctx.db, [(r[0].thread_id, r[0].author_ref) for r in rows])
    out: list[CommentItem] = []
    for row, thread_id, code, title, subject in rows:
        snippet = ftext.excerpt(ftext.plain_text(row.body_md), SNIPPET)
        if len(snippet) < 12:
            continue
        out.append(
            CommentItem(
                id=f"comment:commons:{row.id}",
                snippet=snippet,
                course=_course_ref(code, title),
                category=_ref(category_for(subject)),
                handle=handles.get((row.thread_id, row.author_ref), "A student"),
                voice="reply",
                source="commons",
                href=_thread_href(int(thread_id)),
                day=row.created_day,
            )
        )
    return out


def _commons_handles(db: Session, keys: list[tuple[int, str | None]]) -> dict[tuple[int, Any], str]:
    wanted = [(t, a) for t, a in keys if a]
    if not wanted:
        return {}
    rows = db.execute(
        sa.select(
            m.CommonsPseudonym.thread_id, m.CommonsPseudonym.author_ref, m.CommonsPseudonym.handle
        ).where(m.CommonsPseudonym.thread_id.in_({t for t, _ in wanted}))
    ).all()
    return {(int(t), a): str(h) for t, a, h in rows}


def _forum_comments(ctx: Ctx, limit: int = 40) -> list[CommentItem]:
    """Forum reviews and discussions: only for a logged-in reader (the forum needs a login)."""
    if not ctx.viewer.logged_in:
        return []
    post, page, course, teacher = m.Post, m.CourseInstructor, m.Course, m.Instructor
    filters = [post.status == "visible"]
    rows = ctx.db.execute(
        sa.select(post, course.code, course.title, course.subject, teacher.slug, m.Pseudonym.handle)
        .join(page, page.id == post.course_instructor_id)
        .join(course, course.id == page.course_id)
        .join(teacher, teacher.id == page.instructor_id)
        .outerjoin(m.Pseudonym, m.Pseudonym.id == post.pseudonym_id)
        .where(*filters)
        .order_by(post.id.desc())
        .limit(limit)
    ).all()
    out: list[CommentItem] = []
    for row, code, title, subject, slug, handle in rows:
        body = f"{row.title}. {row.body_md}" if row.title else row.body_md
        snippet = ftext.excerpt(ftext.plain_text(body), SNIPPET)
        if len(snippet) < 12:
            continue
        href = f"/courses/{quote(code, safe='')}/i/{quote(slug, safe='')}/t/{row.id}"
        out.append(
            CommentItem(
                id=f"comment:post:{row.id}",
                snippet=snippet,
                course=_course_ref(code, title),
                category=_ref(category_for(subject)),
                handle=str(handle) if handle else "A student",
                voice="review" if row.kind == "review" else "discussion",
                source="forum",
                href=href,
                day=row.created_day,
            )
        )
    return out


# ----------------------------------------------------------------------------- items


def _stats(db: Session, codes: Sequence[str]) -> dict[str, CourseStats]:
    if not codes:
        return {}
    rows = db.execute(
        sa.select(m.AttributeValue.subject_id, m.AttributeValue.key, m.AttributeValue.value,
                  m.AttributeValue.n)
        .where(
            m.AttributeValue.subject_type == "course",
            m.AttributeValue.subject_id.in_(codes),
            m.AttributeValue.key.in_(("workload_hours", "difficulty")),
        )
    ).all()  # fmt: skip
    out: dict[str, CourseStats] = {}
    for code, key, value, n in rows:
        stats = out.setdefault(code, CourseStats())
        setattr(stats, key, round(float(value), 1))
        stats.n = max(stats.n, int(n or 0))
    return out


def _commons_counts(db: Session, ids: Sequence[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(
        sa.select(m.CommonsThread.course_id, sa.func.count(m.CommonsThread.id))
        .where(m.CommonsThread.status == "visible", m.CommonsThread.course_id.in_(ids))
        .group_by(m.CommonsThread.course_id)
    ).all()
    return {int(cid): int(n) for cid, n in rows if cid is not None}


def illustration(code: str, subject: str) -> Illustration:
    return Illustration(
        seed=stable("illustration", code) % 2**31,
        motif=motif_for(subject),
        palette=stable("palette", code) % 6,
    )


def course_item(pick: Pick, stats: CourseStats | None = None, commons_count: int = 0) -> CourseItem:
    c = pick.course
    return CourseItem(
        id=f"course:{c.code}",
        code=c.code,
        title=c.title,
        subject=c.subject,
        category=_ref(BY_KEY[c.category]),
        units=c.units,
        excerpt=ftext.excerpt(c.description, EXCERPT),
        core_tags=list(c.core_tags),
        illustration=illustration(c.code, c.subject),
        stats=stats,
        reason=pick.reason,
        commons_count=commons_count,
    )


# ----------------------------------------------------------------------------- entry point


def browse_rows(
    db: Session, account_id: uuid.UUID | None, *, today: dt.date | None = None
) -> tuple[list[CourseItem], list[CommentItem]]:
    """(spotlights, quotes) for the Catalog page. Empty before the catalog is loaded."""
    year = catalog_repo.latest_catalog_year(db)
    if year is None:
        return [], []
    viewer = load_viewer(db, account_id)
    seed = (today or dt.date.today()).isoformat()
    ctx = Ctx(db=db, pool=get_pool(db, year), viewer=viewer, seed=seed)
    picks = _spread(_for_you(ctx))[:SPOTLIGHTS]
    stats = _stats(db, [p.course.code for p in picks])
    counts = _commons_counts(db, [p.course.id for p in picks])
    spotlights = [
        course_item(p, stats.get(p.course.code), counts.get(p.course.id, 0)) for p in picks
    ]
    quotes = _commons_comments(ctx) + _forum_comments(ctx)
    quotes.sort(key=lambda c: (c.day, c.id), reverse=True)
    return spotlights, quotes[:QUOTES]
