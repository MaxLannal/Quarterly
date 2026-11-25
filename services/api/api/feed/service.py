"""The feed's ranking (`GET /feed`): For you, Explore and Following.

The feed is a deterministic stream: the same viewer, tab, categories and day give the same
items in the same order, so a cursor is just {tab, seed, offset} and pages never repeat an item.

- **For you**, logged in: courses whose title or description match the student's interests,
  research areas, future domains, humanities topics, career paths and intended programs (whole
  words; a match in the title counts double), plus route courses, within the focus categories
  if any; then the best of those categories. Logged out (or nothing to go on): a curated
  "best of UChicago" mix across categories (Core courses, approachable levels, rich
  descriptions), rotated daily.
- **Explore**: a daily shuffle across every category, two courses from the categories the
  student has not chosen for every one from those they have.
- **Following**: the courses on the student's routes and the courses and threads they follow,
  with Commons activity on them. Empty when there is nothing to follow.

Courses are spread so no two in a row share a category (when there is a choice), and a card of
another kind (a book from the shelf, a student's comment, a word cloud, an open question, a
program) follows every three or four courses. Every reason line is written by this code, never
by a model; the AI notes (`api.feed.notes`) only add a line next to it.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db import models as m
from api.feed import shelf
from api.feed import text as ftext
from api.feed.categories import BY_KEY, CATEGORIES, Category, category_for, known_keys, motif_for
from api.feed.pool import Pool, PoolCourse, get_pool, jitter, stable
from api.repo import catalog as catalog_repo
from api.schemas.feed import (
    BookItem,
    CommentItem,
    CourseItem,
    CourseRef,
    CourseStats,
    FeedCategories,
    FeedCategory,
    FeedCategoryRef,
    FeedItem,
    FeedPage,
    FeedTab,
    Illustration,
    ProgramItem,
    QuestionItem,
    ShelfBook,
    WeightedWord,
    WordsItem,
)

PAGE_DEFAULT = 12
PAGE_MAX = 24
#: Courses in one day's stream, and items in all (about ten pages).
STREAM_COURSES = 180
STREAM_MAX = 240
SNIPPET = 240
SHELF_NOTE = "A book from the Quarterly shelf, reading for the curious, not a syllabus."
EXCERPT = 300
#: Courses between two cards of another kind: 3, 4, 3, 4, ...
GAPS = (3, 4)
CARD_CYCLE = ("book", "comment", "words", "question", "program", "comment", "book", "words")
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
_PROGRAM_ORDER = {"major": 0, "minor": 0, "core": 1, "bxms": 2, "study_abroad_block": 3}
_PROGRAM_KINDS = {
    "core": "What every College student shares",
    "major": "A major worth a look",
    "minor": "A minor worth a look",
    "bxms": "A path to a master's degree alongside the College",
    "study_abroad_block": "A quarter of civilization studies abroad",
}
MAX_INTERESTS = 16
#: Courses one interest can bring into a day's stream.
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
    #: The profile's saved focus categories.
    saved_focus: list[str] = field(default_factory=list)
    #: Route course code -> the route's title (the chosen route first).
    route_courses: dict[str, str] = field(default_factory=dict)
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
    """What the feed knows about the student: their profile and routes, read directly."""
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
        viewer.saved_focus = known_keys(_strings(profile.feed_categories))
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
    routes = db.scalars(
        sa.select(m.Pathway)
        .where(m.Pathway.account_id == account_id, m.Pathway.status != "archived")
        .order_by((m.Pathway.status == "chosen").desc(), m.Pathway.position, m.Pathway.title)
    ).all()
    for route in routes:
        for entry in route.courses or []:
            code = catalog_repo.normalize_code(str(entry.get("code", ""))) if entry else None
            if code and code not in viewer.route_courses:
                viewer.route_courses[code] = route.title
    return viewer


# ----------------------------------------------------------------------------- the cursor


def encode_cursor(tab: str, seed: str, offset: int) -> str:
    raw = json.dumps({"t": tab, "s": seed, "o": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None, tab: str) -> tuple[str | None, int]:
    """(seed, offset) from a cursor of this tab; (None, 0) for a missing, foreign or broken one."""
    if not cursor:
        return None, 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None, 0
    if not isinstance(data, dict) or data.get("t") != tab:
        return None, 0
    seed, offset = data.get("s"), data.get("o")
    if not isinstance(seed, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", seed):
        return None, 0
    if not isinstance(offset, int) or not 0 <= offset <= STREAM_MAX:
        return None, 0
    return seed, offset


# ----------------------------------------------------------------------------- picks


@dataclass(frozen=True)
class Pick:
    course: PoolCourse
    reason: str
    #: The matched interest, which names the course's theme in the headline; else its title's.
    theme: str | None = None

    @property
    def topic(self) -> str:
        return self.theme or _topic_of(self.course)


@dataclass
class Ctx:
    db: Session
    pool: Pool
    viewer: Viewer
    tab: str
    seed: str
    focus: list[str]


def _ref(cat: Category) -> FeedCategoryRef:
    return FeedCategoryRef(key=cat.key, label=cat.label, motif=cat.motif)


def _topic_of(course: PoolCourse) -> str:
    """The course's topic for the headline ("quantum computing", "Jewish civilization")."""
    return ftext.topic(course.title, course.description)


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
                picks.append(Pick(course, _curated_reason(course, ctx.focus)))
    return picks


def _curated_reason(course: PoolCourse, focus: Sequence[str]) -> str:
    label = BY_KEY[course.category].label
    if course.category in focus:
        return f"In your focus: {label}"
    if course.core_tags:
        if course.category == "core":
            return "In the Core, the College's shared conversation"
        return f"A Core course in {label}"
    return f"Best of UChicago: {label}"


def _explore_reason(category: str, chosen: set[str]) -> str:
    label = BY_KEY[category].label
    return f"More from your focus: {label}" if category in chosen else f"Something new: {label}"


def _for_you(ctx: Ctx) -> list[Pick]:
    """Matches for the student's interests (each interest in turn, so one broad interest
    cannot fill the page), with one curated course after every four; then the curated mix."""
    viewer = ctx.viewer
    categories = ctx.focus or [c.key for c in CATEGORIES]
    allowed = set(categories)
    groups: dict[str, list[tuple[float, Pick]]] = {}
    if viewer.interests or viewer.route_courses or viewer.followed_courses:
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
            if course.code in viewer.route_courses:
                total += 5.0
                reason = _cap(f"On your route '{viewer.route_courses[course.code]}'", 80)
                group = "\x00route"
            elif course.code in viewer.followed_courses:
                total += 3.0
                reason = reason or "You follow this course"
                group = group or "\x00follow"
            if total <= 0:
                continue
            rank = total + 0.3 * course.quality + 0.8 * jitter(ctx.seed, "fy", course.code)
            theme = best.text if best is not None else None
            groups.setdefault(group, []).append((rank, Pick(course, reason, theme)))
    for rows in groups.values():
        rows.sort(key=lambda t: -t[0])
    order = sorted(groups, key=lambda k: (k != "\x00route", -groups[k][0][0]))
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


def _explore(ctx: Ctx) -> list[Pick]:
    chosen = set(ctx.focus or ctx.viewer.saved_focus)
    keys = [c.key for c in CATEGORIES if ctx.pool.by_category.get(c.key)]
    queues: dict[str, list[PoolCourse]] = {}
    for key in keys:
        rows = ctx.pool.by_category[key][:45]  # each category's better half, by quality
        queues[key] = sorted(rows, key=lambda c: jitter(ctx.seed, "explore", c.code))
    picks: list[Pick] = []
    round_no = 0
    while len(picks) < STREAM_COURSES and any(queues.values()):
        turn = [k for k in keys for _ in range(1 if k in chosen else 2)]
        turn.sort(key=lambda k: jitter(ctx.seed, "round", round_no, k, turn.count(k)))
        for key in turn:
            if queues[key] and len(picks) < STREAM_COURSES:
                course = queues[key].pop(0)
                picks.append(Pick(course, _explore_reason(key, chosen)))
        round_no += 1
    return picks


def _following(ctx: Ctx) -> list[Pick]:
    viewer = ctx.viewer
    codes = list(viewer.route_courses) + [
        c for c in viewer.followed_courses if c not in viewer.route_courses
    ]
    found = _courses_by_code(ctx, codes)
    picks: list[Pick] = []
    for code in codes:
        course = found.get(code)
        if course is None:
            continue
        if code in viewer.route_courses:
            reason = _cap(f"On your route '{viewer.route_courses[code]}'", 80)
        else:
            reason = "You follow this course"
        picks.append(Pick(course, reason))
    return picks[:STREAM_COURSES]


def _courses_by_code(ctx: Ctx, codes: Sequence[str]) -> dict[str, PoolCourse]:
    """Pool courses for `codes`; codes outside the pool (graduate, no description) are read
    from the catalog, so a route's every real course can appear."""
    out = {c: ctx.pool.by_code[c] for c in codes if c in ctx.pool.by_code}
    missing = [c for c in codes if c not in out]
    if missing:
        rows = ctx.db.execute(
            sa.select(m.Course).where(
                m.Course.catalog_year == ctx.pool.catalog_year, m.Course.code.in_(missing)
            )
        ).scalars()
        for row in rows:
            title = ftext.squash(row.title)
            description = ftext.squash(row.description or "")
            out[row.code] = PoolCourse(
                id=row.id,
                code=row.code,
                subject=row.subject,
                number=row.number,
                title=title,
                description=description,
                core_tags=tuple(row.core_tags or ()),
                units=row.units,
                category=category_for(row.subject).key,
                low_title=title.lower(),
                low_text=f"{title} {description}".lower(),
                quality=0.0,
            )
    return out


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


# ----------------------------------------------------------------------------- other cards


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
    if ctx.tab == "following":
        ids = _followed_course_ids(ctx)
        filters.append(
            sa.or_(thread.course_id.in_(ids), thread.id.in_(ctx.viewer.followed_threads or [-1]))
        )
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
    if ctx.tab == "following":
        filters.append(page.course_id.in_(_followed_course_ids(ctx)))
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


def _followed_course_ids(ctx: Ctx) -> list[int]:
    codes = list(ctx.viewer.route_courses) + ctx.viewer.followed_courses
    if not codes:
        return [-1]
    ids = ctx.db.scalars(
        sa.select(m.Course.id).where(
            m.Course.code.in_(codes), m.Course.catalog_year == ctx.pool.catalog_year
        )
    ).all()
    return list(ids) or [-1]


def _questions(ctx: Ctx, limit: int = 16) -> list[QuestionItem]:
    thread, course = m.CommonsThread, m.Course
    filters = [thread.status == "visible"]
    if ctx.tab == "following":
        filters.append(
            sa.or_(
                thread.id.in_(ctx.viewer.followed_threads or [-1]),
                thread.course_id.in_(_followed_course_ids(ctx)),
            )
        )
    rows = ctx.db.execute(
        sa.select(thread, course.code, course.title)
        .outerjoin(course, course.id == thread.course_id)
        .where(*filters)
        .order_by((thread.reply_count == 0).desc(), thread.id.desc())
        .limit(limit)
    ).all()
    out: list[QuestionItem] = []
    for row, code, title in rows:
        out.append(
            QuestionItem(
                id=f"question:{row.id}",
                thread_id=row.id,
                title=ftext.excerpt(ftext.squash(row.title), 160),
                snippet=ftext.excerpt(ftext.plain_text(row.body_md or ""), 180),
                course=_course_ref(code, title) if code else None,
                reply_count=row.reply_count,
                answered=row.accepted_reply_id is not None or row.reply_count > 0,
                href=_thread_href(row.id),
                day=row.created_day,
            )
        )
    return out


def _book_links(pool: Pool, book: shelf.Book) -> list[CourseRef]:
    """2-4 real courses that share a book's themes (computed once per pool)."""
    key = f"book:{book.slug}"
    if key in pool.memo:
        cached: list[CourseRef] = pool.memo[key]
        return cached
    keys = shelf.book_keys(book)
    cats = set(book.categories)
    scored: list[tuple[float, PoolCourse]] = []
    for course in pool.courses:
        score = shelf.keyword_score(keys, course.low_title, course.low_text)
        if score == 0:
            continue
        if course.category in cats:
            score += 1
        elif score < 3:
            continue
        scored.append((score + 0.1 * course.quality, course))
    scored.sort(key=lambda t: (-t[0], t[1].code))
    links = [_course_ref(c.code, c.title) for _, c in scored[:4]]
    pool.memo[key] = links
    return links


def _book_item(ctx: Ctx, book: shelf.Book, reason: str) -> BookItem | None:
    courses = _book_links(ctx.pool, book)
    if len(courses) < 2:
        return None
    return BookItem(
        id=book.id,
        book=_shelf_book(book),
        category=_ref(BY_KEY[book.categories[0]]),
        courses=courses,
        reason=reason,
    )


def _shelf_book(book: shelf.Book) -> ShelfBook:
    return ShelfBook(
        id=book.id,
        slug=book.slug,
        title=book.title,
        author=book.author,
        year=book.year,
        when=book.when,
    )


def _books(ctx: Ctx, picks: Sequence[Pick], limit: int = 10) -> list[BookItem]:
    """Shelf books for the categories in this stream (and the student's interests)."""
    weights: dict[str, float] = {}
    for p in picks[:60]:
        weights[p.course.category] = weights.get(p.course.category, 0.0) + 1.0
    scored: list[tuple[float, shelf.Book, str]] = []
    for book in shelf.load_shelf():
        score = sum(weights.get(c, 0.0) for c in book.categories) / 10
        reason = f"From the shelf for {BY_KEY[book.categories[0]].label}"
        for interest in ctx.viewer.interests:
            if any(interest.phrase in k or k in interest.phrase for k in book.keywords):
                score += 3
                reason = _cap(f"For your interest in {interest.text}", 80)
                break
        if score <= 0:
            continue
        scored.append((score + 1.5 * jitter(ctx.seed, "book", book.slug), book, reason))
    scored.sort(key=lambda t: -t[0])
    out: list[BookItem] = []
    for _, book, reason in scored:
        item = _book_item(ctx, book, reason)
        if item is not None:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def _words(ctx: Ctx, picks: Sequence[Pick], limit: int = 8) -> list[WordsItem]:
    order: list[str] = []
    for p in picks:
        if p.course.category not in order:
            order.append(p.course.category)
    out: list[WordsItem] = []
    for key in order[:limit]:
        words = ctx.pool.cloud(key)
        if len(words) < 12:
            continue
        cat = BY_KEY[key]
        out.append(
            WordsItem(
                id=f"words:{key}",
                category=_ref(cat),
                label=cat.label,
                words=[WeightedWord(text=w, weight=wt) for w, wt in words],
            )
        )
    return out


def _programs(ctx: Ctx, limit: int = 8) -> list[ProgramItem]:
    rows = ctx.db.scalars(sa.select(m.Program).order_by(m.Program.id)).all()
    intended = ctx.viewer.intended_programs
    rows = sorted(
        rows,
        key=lambda p: (
            p.id not in intended,
            p.type == "study_abroad_block",
            jitter(ctx.seed, p.id),
        ),
    )
    out: list[ProgramItem] = []
    for row in rows[:limit]:
        if row.id in intended:
            reason = "A program you are considering"
        else:
            reason = _PROGRAM_KINDS.get(row.type, "A program worth a look")
        out.append(
            ProgramItem(
                id=f"program:{row.id}",
                program_id=row.id,
                name=row.name,
                type=row.type,
                department=row.department,
                reason=reason,
            )
        )
    return out


# ----------------------------------------------------------------------------- the stream


Slot = Pick | BookItem | CommentItem | WordsItem | QuestionItem | ProgramItem


def _weave(picks: list[Pick], supply: dict[str, list[Any]], tail: bool) -> list[Slot]:
    """Courses with a card of another kind after every 3 or 4 of them. `tail`: append the cards
    left over once the courses run out (Following, where comments matter as much)."""
    out: list[Slot] = []
    cycle = 0
    since = 0
    gap = 0

    def next_card() -> Slot | None:
        nonlocal cycle
        for step in range(len(CARD_CYCLE)):
            kind = CARD_CYCLE[(cycle + step) % len(CARD_CYCLE)]
            if supply.get(kind):
                cycle = (cycle + step + 1) % len(CARD_CYCLE)
                card: Slot = supply[kind].pop(0)
                return card
        return None

    for pick in picks:
        out.append(pick)
        since += 1
        if since >= GAPS[gap % len(GAPS)]:
            card = next_card()
            if card is not None:
                out.append(card)
            since = 0
            gap += 1
        if len(out) >= STREAM_MAX:
            return out[:STREAM_MAX]
    if tail:
        while len(out) < STREAM_MAX and (card := next_card()) is not None:
            out.append(card)
    return out


def _stream(ctx: Ctx) -> tuple[list[Slot], list[Pick]]:
    if ctx.tab == "following":
        picks = _following(ctx)
    elif ctx.tab == "explore":
        picks = _explore(ctx)
    else:
        picks = _for_you(ctx)
    picks = _spread(picks)
    comments = _commons_comments(ctx) + _forum_comments(ctx)
    comments.sort(key=lambda c: (c.day, c.id), reverse=True)
    if ctx.focus and ctx.tab == "for_you":
        inside = [c for c in comments if c.category.key in ctx.focus]
        comments = inside + [c for c in comments if c.category.key not in ctx.focus]
    if ctx.tab == "following":
        supply: dict[str, list[Any]] = {"comment": comments, "question": _questions(ctx)}
        if picks:
            supply["book"] = _books(ctx, picks, limit=4)
    else:
        supply = {
            "book": _books(ctx, picks),
            "comment": comments,
            "words": _words(ctx, picks),
            "question": _questions(ctx),
            "program": _programs(ctx),
        }
    return _weave(picks, supply, tail=ctx.tab == "following"), picks


def _headline(ctx: Ctx, picks: Sequence[Pick]) -> str:
    topics: list[str] = []
    for p in picks:
        t = p.topic.strip()
        if t and t.casefold() not in {x.casefold() for x in topics}:
            topics.append(t)
        if len(topics) == 3:
            break
    if not topics:
        if ctx.tab == "following":
            return "Nothing to follow yet: keep a route or follow a course"
        return "Today's river is still filling up"
    lead = "On your routes today" if ctx.tab == "following" else "Today's river"
    for n in (3, 2, 1):
        chosen = topics[:n]
        joined = chosen[0] if n == 1 else ", ".join(chosen[:-1]) + " and " + chosen[-1]
        line = f"{lead}: {joined}"
        if len(line) <= 90:
            return line
    return _cap(f"{lead}: {topics[0]}", 90)


# ----------------------------------------------------------------------------- page items


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
        words=ftext.keywords(c.title, c.description, n=8),
        illustration=illustration(c.code, c.subject),
        books=[_shelf_book(b) for b in shelf.books_for_course(c.title, c.description, c.category)],
        stats=stats,
        reason=pick.reason,
        commons_count=commons_count,
    )


def _materialize(db: Session, slots: Sequence[Slot]) -> list[FeedItem]:
    picks = [s for s in slots if isinstance(s, Pick)]
    stats = _stats(db, [p.course.code for p in picks])
    counts = _commons_counts(db, [p.course.id for p in picks])
    items: list[FeedItem] = []
    for slot in slots:
        if isinstance(slot, Pick):
            items.append(
                course_item(slot, stats.get(slot.course.code), counts.get(slot.course.id, 0))
            )
        else:
            items.append(slot)
    return items


# ----------------------------------------------------------------------------- entry points


def applied_categories(viewer: Viewer, categories: str | None) -> list[str]:
    """The request's categories (a comma list) if given, else the profile's saved focus."""
    if categories is not None:
        return known_keys(categories.split(","))
    return list(viewer.saved_focus)


def build_feed(
    db: Session,
    account_id: uuid.UUID | None,
    *,
    tab: FeedTab = "for_you",
    categories: str | None = None,
    cursor: str | None = None,
    limit: int = PAGE_DEFAULT,
    today: dt.date | None = None,
) -> FeedPage:
    limit = max(1, min(limit, PAGE_MAX))
    viewer = load_viewer(db, account_id)
    focus = applied_categories(viewer, categories) if tab != "following" else []
    seed, offset = decode_cursor(cursor, tab)
    seed = seed or (today or dt.date.today()).isoformat()
    year = catalog_repo.latest_catalog_year(db)
    personalized = viewer.logged_in and (
        bool(viewer.interests or viewer.route_courses or viewer.followed_courses) or bool(focus)
    )
    if year is None or (tab == "following" and not viewer.logged_in):
        return FeedPage(
            tab=tab,
            items=[],
            next_cursor=None,
            categories_applied=focus,
            headline=(
                "Log in to follow courses and routes"
                if tab == "following"
                else "The catalog has not been loaded yet"
            ),
            personalized=False,
        )
    ctx = Ctx(db=db, pool=get_pool(db, year), viewer=viewer, tab=tab, seed=seed, focus=focus)
    slots, picks = _stream(ctx)
    page = slots[offset : offset + limit]
    end = offset + len(page)
    return FeedPage(
        tab=tab,
        items=_materialize(db, page),
        next_cursor=encode_cursor(tab, seed, end) if end < len(slots) else None,
        categories_applied=focus,
        headline=_headline(ctx, picks),
        personalized=personalized,
    )


def list_categories(db: Session, account_id: uuid.UUID | None) -> FeedCategories:
    year = catalog_repo.latest_catalog_year(db)
    subjects: dict[str, list[str]] = {c.key: [] for c in CATEGORIES}
    counts: dict[str, int] = {c.key: 0 for c in CATEGORIES}
    if year is not None:
        rows = db.execute(
            sa.select(m.Course.subject).where(m.Course.catalog_year == year).distinct()
        ).scalars()
        for subject in sorted(rows):
            subjects[category_for(subject).key].append(subject)
        pool = get_pool(db, year)
        counts = {key: len(rows) for key, rows in pool.by_category.items()}
    viewer = load_viewer(db, account_id)
    return FeedCategories(
        categories=[
            FeedCategory(
                key=c.key,
                label=c.label,
                motif=c.motif,
                blurb=c.blurb,
                subjects=subjects[c.key],
                course_count=counts.get(c.key, 0),
            )
            for c in CATEGORIES
        ],
        selected=viewer.saved_focus,
    )


# ----------------------------------------------------------------------------- for the notes


@dataclass(frozen=True)
class Described:
    """An item of the page as the notes agent and the fallback see it."""

    id: str
    kind: str
    label: str
    #: Catalog text (a course's excerpt, a book's author and year); never student text.
    detail: str
    #: Student-written text (a question's title), passed to a model only as untrusted data.
    student_text: str | None
    reason: str
    topic: str
    course_codes: tuple[str, ...]


def describe_items(
    db: Session,
    account_id: uuid.UUID | None,
    item_ids: Sequence[str],
    *,
    tab: FeedTab = "for_you",
    categories: str | None = None,
) -> list[Described]:
    """The feed items named by `item_ids`, rebuilt from the database (unknown ids are left
    out), each with the deterministic reason the feed gives it on `tab` for this viewer."""
    viewer = load_viewer(db, account_id)
    year = catalog_repo.latest_catalog_year(db)
    if year is None:
        return []
    focus = applied_categories(viewer, categories) if tab != "following" else []
    ctx = Ctx(
        db=db, pool=get_pool(db, year), viewer=viewer, tab=tab,
        seed=dt.date.today().isoformat(), focus=focus,
    )  # fmt: skip
    out: list[Described] = []
    course_codes = [i.split(":", 1)[1] for i in item_ids if i.startswith("course:")]
    courses = _courses_by_code(ctx, [c for c in course_codes if catalog_repo.normalize_code(c)])
    books = shelf.by_slug()
    for item_id in dict.fromkeys(item_ids):
        kind, _, key = item_id.partition(":")
        if kind == "course" and key in courses:
            c = courses[key]
            pick = _reason_for(ctx, c)
            out.append(
                Described(
                    id=item_id,
                    kind="course",
                    label=f"{c.code} {c.title}",
                    detail=ftext.excerpt(c.description, EXCERPT),
                    student_text=None,
                    reason=pick.reason,
                    topic=pick.topic,
                    course_codes=(c.code,),
                )
            )
        elif kind == "book" and key in books:
            b = books[key]
            out.append(
                Described(
                    id=item_id,
                    kind="book",
                    label=f"{b.title} by {b.author} ({b.when})",
                    detail=SHELF_NOTE,
                    student_text=None,
                    reason=f"From the shelf for {BY_KEY[b.categories[0]].label}",
                    topic=b.title,
                    course_codes=(),
                )
            )
        elif kind == "words" and key in BY_KEY:
            cat = BY_KEY[key]
            words = ", ".join(w for w, _ in ctx.pool.cloud(key)[:12])
            out.append(
                Described(
                    id=item_id,
                    kind="words",
                    label=f"Word cloud: {cat.label}",
                    detail=f"Words from the titles of its courses: {words}.",
                    student_text=None,
                    reason=f"Words from {cat.label}",
                    topic=cat.label,
                    course_codes=(),
                )
            )
        elif kind == "program":
            row = db.get(m.Program, key)
            if row is not None and _program_visible(db, row.id):
                out.append(
                    Described(
                        id=item_id,
                        kind="program",
                        label=f"{row.name} ({row.type.replace('_', ' ')})",
                        detail=f"Department: {row.department or 'the College'}.",
                        student_text=None,
                        reason="A program worth a look",
                        topic=row.name,
                        course_codes=(),
                    )
                )
        elif kind in ("question", "comment"):
            described = _describe_voice(db, item_id, kind, key, viewer)
            if described is not None:
                out.append(described)
    return out


def _describe_voice(
    db: Session, item_id: str, kind: str, key: str, viewer: Viewer
) -> Described | None:
    """A question or comment card: the course it is about (catalog text), and for a question
    its title as student text."""
    thread: m.CommonsThread | None = None
    course: m.Course | None = None
    if kind == "question" and key.isdigit():
        thread = db.get(m.CommonsThread, int(key))
    elif kind == "comment" and key.startswith("commons:") and key[8:].isdigit():
        reply = db.get(m.CommonsReply, int(key[8:]))
        if reply is not None and reply.status == "visible" and reply.kind == "human":
            thread = db.get(m.CommonsThread, reply.thread_id)
    elif kind == "comment" and key.startswith("post:") and key[5:].isdigit() and viewer.logged_in:
        post = db.get(m.Post, int(key[5:]))
        if post is not None and post.status == "visible":
            page = db.get(m.CourseInstructor, post.course_instructor_id)
            course = db.get(m.Course, page.course_id) if page is not None else None
    if thread is not None:
        if thread.status != "visible":
            return None
        course = db.get(m.Course, thread.course_id) if thread.course_id else None
    if thread is None and course is None:
        return None
    about = f"{course.code} {course.title}" if course is not None else "a campus question"
    if kind == "question":
        return Described(
            id=item_id,
            kind="question",
            label=f"An open question in the Forum about {about}",
            detail="A student asked this in the Forum; others can answer.",
            student_text=thread.title if thread is not None else None,
            reason="Can you help? A student is asking",
            topic=course.title if course is not None else "a student's question",
            course_codes=(course.code,) if course is not None else (),
        )
    return Described(
        id=item_id,
        kind="comment",
        label=f"A student's comment about {about}",
        detail="What a student wrote about the course (not shown here).",
        student_text=None,
        reason="A student's voice on this course",
        topic=course.title if course is not None else "a student's voice",
        course_codes=(course.code,) if course is not None else (),
    )


def _reason_for(ctx: Ctx, course: PoolCourse) -> Pick:
    """The reason the feed gives `course` on this tab (the same line as in `build_feed`)."""
    viewer = ctx.viewer
    if ctx.tab == "explore":
        return Pick(course, _explore_reason(course.category, set(ctx.focus or viewer.saved_focus)))
    if course.code in viewer.route_courses:
        route = viewer.route_courses[course.code]
        return Pick(course, _cap(f"On your route '{route}'", 80))
    if ctx.tab == "following":
        return Pick(course, "You follow this course")
    best, best_score, whole = None, 0.0, False
    for interest in viewer.interests:
        s, exact = interest.match(course)
        if s > best_score:
            best, best_score, whole = interest, s, exact
    if best is not None:
        return Pick(course, best.reason if whole else best.near_reason, best.text)
    if course.code in viewer.followed_courses:
        return Pick(course, "You follow this course")
    return Pick(course, _curated_reason(course, ctx.focus))


def default_headline(described: Sequence[Described]) -> str:
    topics: list[str] = []
    for d in described:
        if d.kind == "course" and d.topic.casefold() not in {t.casefold() for t in topics}:
            topics.append(d.topic)
    if not topics:
        topics = [d.topic for d in described[:3]]
    if not topics:
        return "Today's river"
    for n in (3, 2, 1):
        chosen = topics[:n]
        joined = chosen[0] if len(chosen) == 1 else ", ".join(chosen[:-1]) + " and " + chosen[-1]
        line = f"Today's river: {joined}"
        if len(line) <= 90:
            return line
    return _cap(f"Today's river: {topics[0]}", 90)


def _program_visible(db: Session, program_id: str) -> bool:
    """A program the feed may describe: one with a published version, or any program when
    unpublished programs are shown (`show_unpublished_programs`)."""
    from api.config import get_settings

    shown = get_settings().show_unpublished_programs
    statuses = catalog_repo.ALL_STATUSES if shown else catalog_repo.PUBLISHED
    return (
        db.scalar(
            sa.select(m.ProgramVersion.id)
            .where(m.ProgramVersion.program_id == program_id, m.ProgramVersion.status.in_(statuses))
            .limit(1)
        )
        is not None
    )
