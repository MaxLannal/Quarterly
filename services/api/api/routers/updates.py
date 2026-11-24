"""What is new for the student (`/me/updates`), read by the dashboard's "What's new" card.

New Commons threads and replies and new forum reviews, discussions and comments, picked for the
logged-in student: threads they follow or asked, courses they follow, and titles that match
their interests, future domains or research areas. When nothing personal turns up, a few "New
on Quarterly" items fill in. High-water marks in `student_profile.updates_seen` say what is new;
POST /me/updates/seen moves them.

The companion and its AI digest (task `a10_updates_digest`) were removed in issue #15; this list
uses no model.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import quote

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.agents.campus_tools import keywords
from api.auth.sessions import current_account
from api.db import models as m
from api.db.session import get_session
from api.forum.scrub import scrub
from api.schemas.updates import UpdateItem, UpdateKind, UpdatesOut, UpdatesSeen

router = APIRouter(prefix="/me", tags=["updates"])

Db = Annotated[Session, Depends(get_session)]
Me = Annotated[m.Account, Depends(current_account)]

MAX_ITEMS = 30
SCAN = 150
SNIPPET = 160
#: With fewer personal items than this, "New on Quarterly" items fill in.
FILL_BELOW = 4
FILL = 5
#: Without a mark yet, items from the last week count as new.
FIRST_WEEK = 7

#: Which mark an item kind moves.
MARK_OF: dict[str, str] = {
    "thread": "thread",
    "reply": "reply",
    "review": "post",
    "discussion": "post",
    "comment": "comment",
}


# ------------------------------------------------------------------------------ text


_FENCE = re.compile(r"```.*?```", re.DOTALL)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TAG = re.compile(r"<[^>]{0,200}>")
_MARKS = re.compile(r"(^|\s)(#{1,6}|>|[-*+]|\d+\.)\s+", re.MULTILINE)
_EMPH = re.compile(r"(\*\*|__|\*|_|~~|`)")


def plain(markdown: str, limit: int = SNIPPET) -> str:
    """Markdown as one line of plain text, scrubbed, at most `limit` characters."""
    text = _FENCE.sub(" ", markdown)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = _TAG.sub(" ", text)
    text = _MARKS.sub(r"\1", text)
    text = _EMPH.sub("", text)
    text = " ".join(scrub(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def course_href(code: str) -> str:
    return f"/courses/{quote(code, safe='')}"


def forum_thread_href(code: str, slug: str, post_id: int) -> str:
    return f"{course_href(code)}/i/{quote(slug, safe='')}/t/{post_id}"


# ------------------------------------------------------------------------------ interests


@dataclass
class Interests:
    """What the student cares about: followed threads and courses, interest terms; and whether
    a Commons thread is theirs."""

    account_id: uuid.UUID
    threads: set[int]
    followed_courses: set[str]
    terms: list[tuple[str, list[str]]]  # (the interest as written, words to look for)
    own: Callable[[int, str | None], bool]

    def course_reason(self, code: str | None) -> str | None:
        if not code:
            return None
        if code in self.followed_courses:
            return f"About {code}, a course you follow"
        return None

    def interest_reason(self, *texts: str | None) -> str | None:
        hay = " ".join(t for t in texts if t).lower()
        if not hay:
            return None
        for term, words in self.terms:
            if term.lower() in hay or any(re.search(rf"\b{re.escape(w)}", hay) for w in words):
                return f"Matches your interest in {term}"
        return None


def _own_checker(account_id: uuid.UUID) -> Callable[[int, str | None], bool]:
    """`own(thread_id, author_ref)`: whether a Commons author ref is this account's. Without the
    Commons identity module, nothing is the student's own."""
    try:
        from api.commons.identity import commons_ref
    except ImportError:  # the Commons work stream has not landed
        return lambda _thread_id, _ref: False
    cache: dict[int, str] = {}

    def own(thread_id: int, ref: str | None) -> bool:
        if ref is None:
            return False
        if thread_id not in cache:
            cache[thread_id] = commons_ref(account_id, thread_id)
        return cache[thread_id] == ref

    return own


def _codes(values: Iterable[Any]) -> set[str]:
    out = set()
    for v in values:
        code = " ".join(str(v or "").upper().split())
        if re.fullmatch(r"[A-Z]{2,5} \d{5}", code):
            out.add(code)
    return out


def interests_of(db: Session, account: m.Account, profile: m.StudentProfile) -> Interests:
    follows = profile.follows or {}
    threads = {int(t) for t in follows.get("threads", []) if str(t).isdigit()}
    followed = _codes(follows.get("courses", []))
    terms: list[tuple[str, list[str]]] = []
    for raw in [*profile.interests, *profile.future_domains, *profile.research_areas]:
        term = " ".join(str(raw).split())[:60]
        if len(term) < 3 or any(term.lower() == t.lower() for t, _ in terms):
            continue
        words = [w for w in keywords(term) if len(w) >= 5]
        terms.append((term, words))
    return Interests(
        account_id=account.id,
        threads=threads,
        followed_courses=followed,
        terms=terms[:12],
        own=_own_checker(account.id),
    )


# ------------------------------------------------------------------------------ collecting


@dataclass
class Candidate:
    kind: UpdateKind
    id: int
    title: str
    snippet: str
    course_code: str | None
    href: str
    day: dt.date
    reason: str
    personal: bool


def _commons(db: Session, me: Interests) -> list[Candidate]:
    thread, reply = m.CommonsThread, m.CommonsReply
    found: list[Candidate] = []
    rows = db.execute(
        sa.select(reply, thread.title, thread.author_ref, m.Course.code, m.Course.title)
        .join(thread, thread.id == reply.thread_id)
        .outerjoin(m.Course, m.Course.id == thread.course_id)
        .where(reply.status == "visible", thread.status == "visible")
        .order_by(reply.id.desc())
        .limit(SCAN)
    ).all()
    for r, title, thread_author, code, course_title in rows:
        if r.kind == "human" and me.own(r.thread_id, r.author_ref):
            continue  # the student's own reply
        if r.thread_id in me.threads:
            reason = "On a thread you follow"
        elif me.own(r.thread_id, thread_author):
            reason = "A reply to your question"
        else:
            reason = me.course_reason(code) or me.interest_reason(title, course_title) or ""
        if not reason:
            continue
        who = "The forum bot answered" if r.kind == "bot" else "New reply"
        found.append(
            Candidate(
                kind="reply",
                id=r.id,
                title=f"{who}: {plain(title, 100)}",
                snippet=plain(r.body_md),
                course_code=code,
                href=f"/forum/t/{r.thread_id}#reply-{r.id}",
                day=r.created_day,
                reason=reason,
                personal=True,
            )
        )
    for t, code, course_title in db.execute(
        sa.select(thread, m.Course.code, m.Course.title)
        .outerjoin(m.Course, m.Course.id == thread.course_id)
        .where(thread.status == "visible")
        .order_by(thread.id.desc())
        .limit(SCAN)
    ).all():
        if me.own(t.id, t.author_ref):
            continue
        followed = "On a thread you follow" if t.id in me.threads else None
        thread_reason = (
            followed
            or me.course_reason(code)
            or me.interest_reason(t.title, t.body_md, " ".join(t.tags), course_title)
        )
        found.append(
            Candidate(
                kind="thread",
                id=t.id,
                title=plain(t.title, 120),
                snippet=plain(t.body_md),
                course_code=code,
                href=f"/forum/t/{t.id}",
                day=t.created_day,
                reason=thread_reason or "New on Quarterly",
                personal=thread_reason is not None,
            )
        )
    return found


def _forum(db: Session, me: Interests) -> list[Candidate]:
    found: list[Candidate] = []
    page = (
        sa.select(m.CourseInstructor.id, m.Course.code, m.Course.title, m.Instructor.slug)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .subquery()
    )
    for post, code, course_title, slug in db.execute(
        sa.select(m.Post, page.c.code, page.c.title, page.c.slug)
        .join(page, page.c.id == m.Post.course_instructor_id)
        .where(m.Post.status == "visible")
        .order_by(m.Post.id.desc())
        .limit(SCAN)
    ).all():
        reason = me.course_reason(code) or me.interest_reason(course_title, post.title)
        kind: UpdateKind = "review" if post.kind == "review" else "discussion"
        heading = post.title or ("A new review" if kind == "review" else "A new discussion")
        found.append(
            Candidate(
                kind=kind,
                id=post.id,
                title=f"{plain(heading, 100)} · {code}",
                snippet=plain(post.body_md),
                course_code=code,
                href=forum_thread_href(code, slug, post.id),
                day=post.created_day,
                reason=reason or "New on Quarterly",
                personal=reason is not None,
            )
        )
    for comment, post_id, code, course_title, slug in db.execute(
        sa.select(m.Comment, m.Post.id, page.c.code, page.c.title, page.c.slug)
        .join(m.Post, m.Post.id == m.Comment.post_id)
        .join(page, page.c.id == m.Post.course_instructor_id)
        .where(m.Comment.status == "visible", m.Post.status == "visible")
        .order_by(m.Comment.id.desc())
        .limit(SCAN)
    ).all():
        reason = me.course_reason(code) or me.interest_reason(course_title)
        if not reason:
            continue  # comments are shown only when they concern the student
        found.append(
            Candidate(
                kind="comment",
                id=comment.id,
                title=f"New comment on {code}",
                snippet=plain(comment.body_md),
                course_code=code,
                href=forum_thread_href(code, slug, post_id),
                day=comment.created_day,
                reason=reason,
                personal=True,
            )
        )
    return found


def _marks(profile: m.StudentProfile) -> dict[str, int]:
    marks: dict[str, int] = {}
    for key, value in (profile.updates_seen or {}).items():
        if key in ("thread", "reply", "post", "comment") and isinstance(value, int):
            marks[key] = value
    return marks


def collect(db: Session, account: m.Account, profile: m.StudentProfile) -> list[UpdateItem]:
    me = interests_of(db, account, profile)
    candidates = _commons(db, me) + _forum(db, me)
    personal = [c for c in candidates if c.personal]
    general = [c for c in candidates if not c.personal]
    picked = list(personal)
    if len(personal) < FILL_BELOW:
        general.sort(key=lambda c: (c.day, c.id), reverse=True)
        picked += general[:FILL]
    picked.sort(key=lambda c: (c.day, c.id), reverse=True)
    marks = _marks(profile)
    week = dt.date.today() - dt.timedelta(days=FIRST_WEEK)
    items = []
    for c in picked[:MAX_ITEMS]:
        mark = marks.get(MARK_OF[c.kind])
        is_new = c.id > mark if mark is not None else c.day >= week
        items.append(
            UpdateItem(
                kind=c.kind,
                id=c.id,
                title=c.title or "Untitled",
                snippet=c.snippet,
                course_code=c.course_code,
                href=c.href,
                day=c.day,
                reason=c.reason,
                is_new=is_new,
            )
        )
    return items


def profile_of(db: Session, account: m.Account) -> m.StudentProfile:
    """The account's profile row, created (empty) the first time it is needed; safe when the
    dashboard creates it at the same moment (`ensure_profile` ignores the conflict)."""
    from api.profile_data import ensure_profile

    return ensure_profile(db, account.id)


# ------------------------------------------------------------------------------ endpoints


@router.get("/updates", response_model=UpdatesOut)
def updates(db: Db, me: Me) -> UpdatesOut:
    # What is new for the logged-in student (the dashboard's "What's new" card).
    profile = profile_of(db, me)
    items = collect(db, me, profile)
    db.commit()
    return UpdatesOut(items=items, unread=sum(1 for i in items if i.is_new))


def _maxima(db: Session) -> dict[str, int]:
    def top(column: Any) -> int:
        return int(db.scalar(sa.select(sa.func.max(column))) or 0)

    return {
        "thread": top(m.CommonsThread.id),
        "reply": top(m.CommonsReply.id),
        "post": top(m.Post.id),
        "comment": top(m.Comment.id),
    }


@router.post("/updates/seen", response_model=UpdatesSeen)
def updates_seen(db: Db, me: Me, body: UpdatesSeen | None = None) -> UpdatesSeen:
    # The student saw the updates: move the marks (default: the newest ids there are).
    profile = profile_of(db, me)
    maxima = _maxima(db)
    asked = body.model_dump() if body is not None else {}
    marks = _marks(profile)
    for key, newest in maxima.items():
        wanted = asked.get(key)
        value = min(wanted, newest) if wanted is not None else newest
        marks[key] = max(marks.get(key, 0), value)
    profile.updates_seen = dict(marks)
    profile.updated_day = dt.date.today()
    db.commit()
    return UpdatesSeen.model_validate(marks)
