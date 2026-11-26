"""The list on `/forum` (issue #20): course reviews and Commons discussions, newest first.

D2 (Richard, 2026-11-24): reviews (`post` + `review_rating`) and discussions (`commons_thread`)
keep their own tables; this module only reads both and merges them. Each source is read in the
same order, newest day first, then discussions before reviews on the same day, then the newest
id; the cursor is the sort key of the last item sent ("2026-11-20.1.345"), so a page never
repeats or skips an item when new ones arrive.

Reviews are for logged-in readers only (SPEC sitemap): a logged-out reader gets discussions
only and `reviews_hidden`. Filters: item type, course (a review matches every code of its
cross-listed course), instructor (reviews only: a discussion has no instructor), subject, text,
and the Commons-only tag and "my questions" (both leave reviews out).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.auth.hashing import author_ref
from api.commons import service as commons
from api.commons.service import Viewer
from api.commons.words import limit_words
from api.db import models as m
from api.forum.pages import crosslisted_codes, instructor_summary
from api.forum.pseudonyms import DELETED
from api.repo.catalog import normalize_code
from api.schemas.board import ForumDiscussionItem, ForumItemList, ForumReviewItem, ItemType
from api.schemas.commons import CommonsCourse, CommonsThreadSummary

PAGE_MAX = 30
#: On the same day, discussions come before reviews.
RANK = {"review": 0, "discussion": 1}
_CURSOR = re.compile(r"^(\d{4}-\d{2}-\d{2})\.([01])\.(\d{1,12})$")

Key = tuple[dt.date, int, int]


def _decode(cursor: str | None) -> Key | None:
    if not cursor:
        return None
    match = _CURSOR.match(cursor)
    if match is None:
        raise HTTPException(status_code=422, detail="Bad cursor.")
    try:
        day = dt.date.fromisoformat(match.group(1))
    except ValueError:
        raise HTTPException(status_code=422, detail="Bad cursor.") from None
    return day, int(match.group(2)), int(match.group(3))


def _encode(key: Key) -> str:
    return f"{key[0].isoformat()}.{key[1]}.{key[2]}"


def _after(day: Any, id_: Any, rank: int, key: Key | None) -> Any:
    """Rows of the source with `rank` that come after `key` in the list's order."""
    if key is None:
        return sa.true()
    k_day, k_rank, k_id = key
    if rank < k_rank:
        return day <= k_day
    if rank > k_rank:
        return day < k_day
    return sa.or_(day < k_day, sa.and_(day == k_day, id_ < k_id))


@dataclass
class _Entry:
    key: Key
    item: ForumReviewItem | ForumDiscussionItem


# ------------------------------------------------------------------------------ discussions


def _discussions(
    db: Session,
    viewer: Viewer,
    where: list[Any],
    key: Key | None,
    limit: int,
) -> tuple[list[_Entry], int]:
    t = m.CommonsThread
    stmt, _, _ = commons._summary_query()
    total = int(
        db.scalar(sa.select(sa.func.count()).select_from(stmt.where(*where).subquery())) or 0
    )
    rank = RANK["discussion"]
    rows = db.execute(
        stmt.where(*where, _after(t.created_day, t.id, rank, key))
        .order_by(t.created_day.desc(), t.id.desc())
        .limit(limit)
    ).all()
    refs = {row[0].id: viewer.ref(row[0].id) for row in rows} if viewer.account else {}
    votes = commons._my_votes(db, viewer, "thread", {k: v for k, v in refs.items() if v})
    answers = _ai_answers(db, [row[0].id for row in rows])
    out = []
    for row in rows:
        thread: m.CommonsThread = row[0]
        summary = CommonsThreadSummary(
            **commons._summary(row, viewer=viewer, my_vote=votes.get(thread.id, 0))
        )
        out.append(
            _Entry(
                key=(thread.created_day, rank, thread.id),
                item=ForumDiscussionItem(thread=summary, ai_answer_html=answers.get(thread.id)),
            )
        )
    return out, total


def _ai_answers(db: Session, thread_ids: Sequence[int]) -> dict[int, str]:
    """The AI's top-level answer of each thread, clipped to the word limit and rendered."""
    if not thread_ids:
        return {}
    r = m.CommonsReply
    rows = db.execute(
        sa.select(r.thread_id, r.body_md)
        .where(
            r.thread_id.in_(thread_ids),
            r.kind == "bot",
            r.parent_id.is_(None),
            r.status == "visible",
        )
        .order_by(r.thread_id, r.id)
    ).all()
    out: dict[int, str] = {}
    for thread_id, body in rows:
        if thread_id not in out:
            out[thread_id] = commons.render(db, limit_words(body))
    return out


# ---------------------------------------------------------------------------------- reviews


def _review_where(
    db: Session,
    *,
    course: str | None,
    instructor: str | None,
    subject: str | None,
    q: str | None,
) -> list[Any] | None:
    p = m.Post
    where: list[Any] = [p.kind == "review", p.status == "visible"]
    if course:
        code = normalize_code(course)
        if code is None:
            return None
        where.append(m.Course.code.in_(crosslisted_codes(db, code)))
    if instructor:
        where.append(m.Instructor.slug == instructor.strip().lower()[:128])
    if subject:
        where.append(m.Course.subject == subject.strip().upper()[:8])
    text = " ".join((q or "").split())[:120]
    if text:

        def hit(word: str) -> Any:
            return sa.or_(
                sa.func.coalesce(p.title, "").icontains(word, autoescape=True),
                p.body_md.icontains(word, autoescape=True),
                m.Course.code.icontains(word, autoescape=True),
                m.Instructor.display_name.icontains(word, autoescape=True),
            )

        words = [w for w in text.split() if len(w) >= 2][:6]
        where.append(sa.or_(hit(text), sa.and_(*(hit(w) for w in words))) if words else hit(text))
    return where


def _review_query() -> Any:
    p = m.Post
    comments = (
        sa.select(m.Comment.post_id.label("post_id"), sa.func.count().label("n"))
        .where(m.Comment.status == "visible")
        .group_by(m.Comment.post_id)
        .subquery()
    )
    return (
        sa.select(
            p,
            m.ReviewRating,
            m.Pseudonym.handle,
            m.Course.code,
            m.Course.title,
            m.Instructor,
            sa.func.coalesce(comments.c.n, 0),
        )
        .join(m.ReviewRating, m.ReviewRating.post_id == p.id)
        .join(m.CourseInstructor, m.CourseInstructor.id == p.course_instructor_id)
        .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .outerjoin(m.Pseudonym, m.Pseudonym.id == p.pseudonym_id)
        .outerjoin(comments, comments.c.post_id == p.id)
    )


def _reviews(
    db: Session,
    account: m.Account,
    where: list[Any],
    key: Key | None,
    limit: int,
) -> tuple[list[_Entry], int]:
    p = m.Post
    stmt = _review_query()
    total = int(
        db.scalar(sa.select(sa.func.count()).select_from(stmt.where(*where).subquery())) or 0
    )
    rank = RANK["review"]
    rows = db.execute(
        stmt.where(*where, _after(p.created_day, p.id, rank, key))
        .order_by(p.created_day.desc(), p.id.desc())
        .limit(limit)
    ).all()
    refs = {row[0].id: author_ref(account.id, row[0].course_instructor_id) for row in rows}
    votes: dict[int, int] = {}
    if refs:
        for target, voter, value in db.execute(
            sa.select(m.Vote.target_id, m.Vote.voter_ref, m.Vote.value).where(
                m.Vote.target_type == "post",
                m.Vote.target_id.in_(list(refs)),
                m.Vote.voter_ref.in_(set(refs.values())),
            )
        ):
            if refs.get(target) == voter:
                votes[target] = int(value)
    out = []
    for post, rating, handle, code, title, teacher, n_comments in rows:
        out.append(
            _Entry(
                key=(post.created_day, rank, post.id),
                item=ForumReviewItem(
                    id=post.id,
                    page_id=post.course_instructor_id,
                    course=CommonsCourse(code=code, title=title),
                    instructor=instructor_summary(teacher),
                    title=post.title,
                    excerpt=commons.excerpt(post.body_md),
                    handle=DELETED if post.author_ref is None else (handle or "Anonymous"),
                    term_taken=post.term_taken,
                    overall=rating.overall,
                    difficulty=rating.difficulty,
                    workload_hours=rating.workload_hours,
                    would_recommend=rating.would_recommend,
                    score=post.score,
                    my_vote=votes.get(post.id, 0),
                    is_mine=post.author_ref is not None and post.author_ref == refs[post.id],
                    n_comments=int(n_comments),
                    created_day=post.created_day,
                    edited_day=post.edited_day,
                ),
            )
        )
    return out, total


# ------------------------------------------------------------------------------------ list


def list_items(
    db: Session,
    viewer: Viewer,
    *,
    item_type: ItemType | None = None,
    course: str | None = None,
    instructor: str | None = None,
    subject: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    mine: bool = False,
    cursor: str | None = None,
    limit: int = 20,
) -> ForumItemList:
    limit = max(1, min(limit, PAGE_MAX))
    key = _decode(cursor)
    hidden = viewer.account is None
    entries: list[_Entry] = []
    total = 0
    if item_type != "review" and not instructor:
        where = commons.thread_filters(
            db, viewer, course=course, subject=subject, tag=tag, q=q, mine=mine
        )
        if where is not None:
            found, n = _discussions(db, viewer, where, key, limit + 1)
            entries += found
            total += n
    if item_type != "discussion" and viewer.account is not None and not tag and not mine:
        where = _review_where(db, course=course, instructor=instructor, subject=subject, q=q)
        if where is not None:
            found, n = _reviews(db, viewer.account, where, key, limit + 1)
            entries += found
            total += n
    entries.sort(key=lambda e: e.key, reverse=True)
    page = entries[:limit]
    more = len(entries) > limit
    return ForumItemList(
        items=[e.item for e in page],
        next_cursor=_encode(page[-1].key) if more and page else None,
        total=total,
        reviews_hidden=hidden,
    )
