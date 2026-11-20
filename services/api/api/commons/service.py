"""Threads, replies, votes, acceptance, follows, presence and reports of the Commons
(docs/BEST-OF-UCHICAGO-PLAN.md).

Identity: authors, voters and reporters are stored as `commons_ref(account_id, thread_id)`; the
account id never reaches a Commons row, and "mine" is decided by recomputing the reader's ref
for the thread. Readers see per-thread random handles ("Quiet Heron"), an OP mark on the asker's
replies, and "Quarterly AI" on the bot's.

Reading is public (logged-out readers see every visible thread, like the catalog); writing needs
a login and an account allowed to write (`ensure_can_write`, shared with the forum).
"""

from __future__ import annotations

import datetime as dt
import html
import re
import secrets
import time
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from api.agents.live import CAMPUS_YEAR, course_codes_in, normalize_code
from api.auth.store import Store
from api.commons.identity import commons_ref, presence_key
from api.db import models as m
from api.forum.markdown import render_markdown
from api.forum.pseudonyms import DELETED, random_handle
from api.forum.scrub import scrub
from api.forum.service import ensure_can_write
from api.schemas.commons import (
    CommonsAcceptOut,
    CommonsCitation,
    CommonsCourse,
    CommonsFollowOut,
    CommonsPresence,
    CommonsReply,
    CommonsReplyCreate,
    CommonsReplyPosted,
    CommonsReplyUpdate,
    CommonsReportIn,
    CommonsReportOut,
    CommonsThreadCreate,
    CommonsThreadDetail,
    CommonsThreadList,
    CommonsThreadSummary,
    CommonsThreadUpdate,
    CommonsVoteIn,
    CommonsVoteOut,
    Sort,
)

BOT_HANDLE = "Quarterly AI"
DELETED_BODY = "[deleted]"
REMOVED_BODY = "[removed]"
#: Replies nest at most this deep; a reply to a reply at this depth becomes its sibling.
MAX_DEPTH = 4
PAGE_MAX = 30
EXCERPT_CHARS = 200
#: "@quarterly" or "@ai" in a reply asks the bot to answer under it.
SUMMON = re.compile(r"(?<![\w@])@(?:quarterly|ai)\b", re.IGNORECASE)
TYPING_TTL_S = 8


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def not_found(what: str = "Question") -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found.")


def summons_bot(text: str) -> bool:
    return SUMMON.search(text) is not None


# ----------------------------------------------------------------------------- text helpers

_MD_NOISE = (
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"^\s{0,3}(?:[>#]+|[-*+]|\d+[.)])\s+", re.MULTILINE), ""),
    (re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1"), r"\2"),
)


def excerpt(body_md: str, limit: int = EXCERPT_CHARS) -> str:
    """Plain text of a markdown body, at most `limit` characters (cut at a word, with "…")."""
    text = body_md
    for pattern, repl in _MD_NOISE:
        text = pattern.sub(repl, text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:")
    return cut + "…"


_TAG_OR_TEXT = re.compile(r"(<[^>]+>)")
_CODE_IN_TEXT = re.compile(r"\b([A-Z]{2,5}) ?(\d{5})\b")


def link_courses(body_html: str, codes: Iterable[str]) -> str:
    """Wrap mentions of real course codes in `body_html` (already sanitized) in links to their
    course pages. Only text outside links and code is touched; the codes come from the
    catalog, so the inserted markup is letters, digits and a space."""
    known = set(codes)
    if not known:
        return body_html
    out: list[str] = []
    skip = 0  # inside <a>, <code> or <pre>
    for part in _TAG_OR_TEXT.split(body_html):
        if part.startswith("<"):
            name = part[1:].lstrip("/").split(" ", 1)[0].split(">", 1)[0].lower()
            if name in ("a", "code", "pre"):
                skip += -1 if part.startswith("</") else 1
                skip = max(skip, 0)
            out.append(part)
            continue
        if skip or not part:
            out.append(part)
            continue

        def repl(match: re.Match[str]) -> str:
            code = f"{match.group(1)} {match.group(2)}"
            if code not in known:
                return match.group(0)
            href = "/courses/" + code.replace(" ", "%20")
            return f'<a href="{href}" data-course="{code}">{html.escape(match.group(0))}</a>'

        out.append(_CODE_IN_TEXT.sub(repl, part))
    return "".join(out)


def render(db: Session, body_md: str) -> str:
    """Safe HTML of a body, with real course codes linked."""
    return link_courses(render_markdown(body_md), course_codes_in(db, body_md, limit=24))


# --------------------------------------------------------------------------------- viewers


@dataclass(frozen=True)
class Viewer:
    """Who reads: an account, or a logged-out visitor."""

    account: m.Account | None

    def ref(self, thread_id: int) -> str | None:
        return commons_ref(self.account.id, thread_id) if self.account is not None else None

    def require(self) -> m.Account:
        if self.account is None:
            raise HTTPException(status_code=401, detail="Log in to continue.")
        return self.account


# ------------------------------------------------------------------------------- pseudonyms


def handle_for(db: Session, thread_id: int, ref: str) -> str:
    """The handle of `ref` on `thread_id`, drawn on first use. Safe under concurrent first
    posts: a conflict on either unique key is ignored and the row read back."""
    for attempt in range(64):
        existing = db.scalar(
            sa.select(m.CommonsPseudonym.handle).where(
                m.CommonsPseudonym.thread_id == thread_id, m.CommonsPseudonym.author_ref == ref
            )
        )
        if existing is not None:
            return existing
        handle = random_handle()
        if attempt >= 48:  # ~4,000 handles per thread; past that, add a number
            handle = f"{handle} {secrets.randbelow(9000) + 1000}"
        db.execute(
            insert(m.CommonsPseudonym)
            .values(thread_id=thread_id, author_ref=ref, handle=handle)
            .on_conflict_do_nothing()
        )
    raise RuntimeError("could not draw a free handle")


def _handles(db: Session, thread_id: int) -> dict[str, str]:
    rows = db.execute(
        sa.select(m.CommonsPseudonym.author_ref, m.CommonsPseudonym.handle).where(
            m.CommonsPseudonym.thread_id == thread_id
        )
    )
    return {ref: handle for ref, handle in rows}


# ---------------------------------------------------------------------------------- courses


def find_course(db: Session, code: str) -> m.Course:
    """The catalog course of `code` ("cmsc14100" works), or 422."""
    normal = normalize_code(code)
    course = (
        db.scalar(
            sa.select(m.Course).where(m.Course.catalog_year == CAMPUS_YEAR, m.Course.code == normal)
        )
        if normal
        else None
    )
    if course is None:
        raise HTTPException(status_code=422, detail=f"There is no course {code.strip()[:16]}.")
    return course


def _course_out(code: str | None, title: str | None) -> CommonsCourse | None:
    return CommonsCourse(code=code, title=title or "") if code else None


# ---------------------------------------------------------------------------------- listing


def _answers_subquery() -> Any:
    return (
        sa.select(m.CommonsReply.thread_id.label("thread_id"), sa.func.count().label("n"))
        .where(
            m.CommonsReply.kind == "human",
            m.CommonsReply.depth == 0,
            m.CommonsReply.status == "visible",
        )
        .group_by(m.CommonsReply.thread_id)
        .subquery()
    )


def _has_bot(thread_id: Any) -> Any:
    return sa.exists().where(
        m.CommonsReply.thread_id == thread_id,
        m.CommonsReply.kind == "bot",
        m.CommonsReply.parent_id.is_(None),
        m.CommonsReply.status == "visible",
    )


def _summary_query() -> tuple[Any, Any, Any]:
    """(select, answers count column, answered expression) over visible-or-not threads."""
    t = m.CommonsThread
    answers = _answers_subquery()
    n_answers = sa.func.coalesce(answers.c.n, 0)
    answered = sa.or_(t.accepted_reply_id.is_not(None), n_answers > 0)
    stmt = (
        sa.select(
            t,
            m.Course.code,
            m.Course.title,
            n_answers.label("n_answers"),
            _has_bot(t.id).label("has_bot"),
            m.CommonsPseudonym.handle,
        )
        .outerjoin(m.Course, m.Course.id == t.course_id)
        .outerjoin(answers, answers.c.thread_id == t.id)
        .outerjoin(
            m.CommonsPseudonym,
            sa.and_(
                m.CommonsPseudonym.thread_id == t.id, m.CommonsPseudonym.author_ref == t.author_ref
            ),
        )
    )
    return stmt, n_answers, answered


def _order(sort: Sort, n_answers: Any) -> list[Any]:
    t = m.CommonsThread
    if sort == "top":
        return [t.score.desc(), t.reply_count.desc(), t.id.desc()]
    if sort == "hot":
        age = sa.cast(sa.func.current_date() - t.created_day, sa.Float) + 2.0
        heat = (t.score + 2 * t.reply_count + n_answers + 1) / sa.func.power(age, 1.5)
        return [heat.desc(), t.id.desc()]
    if sort == "active":
        last = aliased(m.CommonsReply)
        latest_day = sa.select(last.created_day).where(last.id == t.last_reply_id).scalar_subquery()
        return [
            sa.func.coalesce(latest_day, t.created_day).desc(),
            sa.func.coalesce(t.last_reply_id, 0).desc(),
            t.id.desc(),
        ]
    return [t.id.desc()]  # new, unanswered


def _my_votes(
    db: Session, viewer: Viewer, target_type: str, refs_by_target: dict[int, str]
) -> dict[int, int]:
    if viewer.account is None or not refs_by_target:
        return {}
    rows = db.execute(
        sa.select(m.CommonsVote.target_id, m.CommonsVote.voter_ref, m.CommonsVote.value).where(
            m.CommonsVote.target_type == target_type,
            m.CommonsVote.target_id.in_(list(refs_by_target)),
            m.CommonsVote.voter_ref.in_(set(refs_by_target.values())),
        )
    )
    return {tid: int(v) for tid, ref, v in rows if refs_by_target.get(tid) == ref}


def _my_thread_ids(db: Session, account: m.Account) -> list[int]:
    """Ids of the account's threads: refs are per thread, so they are recomputed for each."""
    rows = db.execute(
        sa.select(m.CommonsThread.id, m.CommonsThread.author_ref).where(
            m.CommonsThread.author_ref.is_not(None)
        )
    )
    return [tid for tid, ref in rows if ref == commons_ref(account.id, tid)]


def _summary(row: Any, *, viewer: Viewer, my_vote: int) -> dict[str, Any]:
    thread: m.CommonsThread = row[0]
    code, title, n_answers, has_bot, handle = row[1], row[2], int(row[3]), bool(row[4]), row[5]
    ref = viewer.ref(thread.id)
    mine = ref is not None and thread.author_ref == ref
    return {
        "id": thread.id,
        "title": thread.title,
        "excerpt": excerpt(thread.body_md),
        "course": _course_out(code, title),
        "tags": list(thread.tags or []),
        "score": thread.score,
        "reply_count": thread.reply_count,
        "answer_count": n_answers,
        "answered": thread.accepted_reply_id is not None or n_answers > 0,
        "accepted": thread.accepted_reply_id is not None,
        "bot_state": thread.bot_state,
        "has_bot_answer": has_bot,
        "handle": DELETED if thread.author_ref is None else (handle or "Anonymous"),
        "is_mine": mine,
        "my_vote": my_vote,
        "status": thread.status,
        "created_day": thread.created_day,
        "edited_day": thread.edited_day,
    }


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(cursor)
    except ValueError:
        raise HTTPException(status_code=422, detail="Bad cursor.") from None
    if offset < 0:
        raise HTTPException(status_code=422, detail="Bad cursor.")
    return offset


def _matches(text: str) -> Any:
    """The whole phrase, or every word of it, in the title, the details or the course code."""
    t = m.CommonsThread

    def hit(word: str) -> Any:
        return sa.or_(
            t.title.icontains(word, autoescape=True),
            t.body_md.icontains(word, autoescape=True),
            sa.func.coalesce(m.Course.code, "").icontains(word, autoescape=True),
        )

    words = [w for w in text.split() if len(w) >= 2][:6]
    return sa.or_(hit(text), sa.and_(*(hit(w) for w in words))) if words else hit(text)


def list_threads(
    db: Session,
    viewer: Viewer,
    *,
    sort: Sort = "hot",
    course: str | None = None,
    subject: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    mine: bool = False,
    cursor: str | None = None,
    limit: int = 20,
) -> CommonsThreadList:
    t = m.CommonsThread
    limit = max(1, min(limit, PAGE_MAX))
    offset = _decode_cursor(cursor)
    stmt, n_answers, answered = _summary_query()
    where: list[Any] = [t.status == "visible"]
    if course:
        code = normalize_code(course)
        if code is None:
            return CommonsThreadList(items=[], next_cursor=None, total=0)
        where.append(m.Course.code == code)
    if subject:
        where.append(m.Course.subject == subject.strip().upper()[:8])
    if tag:
        where.append(sa.literal(tag.strip().lower()[:24], sa.Text) == sa.any_(t.tags))
    text = " ".join((q or "").split())[:120]
    if text:
        where.append(_matches(text))
    if mine:
        account = viewer.require()
        where.append(t.id.in_(_my_thread_ids(db, account) or [-1]))
    if sort == "unanswered":
        where.append(sa.not_(answered))
    filtered = stmt.where(*where)
    total = int(db.scalar(sa.select(sa.func.count()).select_from(filtered.subquery())) or 0)
    rows = db.execute(filtered.order_by(*_order(sort, n_answers)).limit(limit).offset(offset)).all()
    refs = {row[0].id: viewer.ref(row[0].id) for row in rows} if viewer.account else {}
    votes = _my_votes(db, viewer, "thread", {k: v for k, v in refs.items() if v})
    items = [
        CommonsThreadSummary(**_summary(row, viewer=viewer, my_vote=votes.get(row[0].id, 0)))
        for row in rows
    ]
    more = offset + len(items) < total
    return CommonsThreadList(
        items=items, next_cursor=str(offset + len(items)) if more else None, total=total
    )


# ---------------------------------------------------------------------------------- threads


def _visible_thread(db: Session, thread_id: int, *, lock: bool = False) -> m.CommonsThread:
    stmt = sa.select(m.CommonsThread).where(m.CommonsThread.id == thread_id)
    if lock:
        stmt = stmt.with_for_update()
    thread = db.scalar(stmt)
    if thread is None or thread.status != "visible":
        raise not_found()
    return thread


def _own_thread(db: Session, account: m.Account, thread_id: int) -> m.CommonsThread:
    thread = db.get(m.CommonsThread, thread_id)
    ref = commons_ref(account.id, thread_id)
    if thread is None:
        raise not_found()
    if thread.author_ref != ref:
        if thread.status != "visible":
            raise not_found()
        raise HTTPException(status_code=403, detail="You can only change your own question.")
    if thread.status != "visible":
        raise HTTPException(status_code=409, detail="This question was deleted.")
    return thread


def _following(db: Session, viewer: Viewer, thread_id: int) -> bool:
    if viewer.account is None:
        return False
    profile = db.get(m.StudentProfile, viewer.account.id)
    threads = (profile.follows or {}).get("threads", []) if profile is not None else []
    return thread_id in threads


def _citations(raw: list[dict[str, Any]]) -> list[CommonsCitation]:
    out = []
    for item in raw or []:
        try:
            out.append(CommonsCitation.model_validate(item))
        except ValueError:
            continue
    return out


def reply_out(
    db: Session,
    reply: m.CommonsReply,
    *,
    thread: m.CommonsThread,
    handles: dict[str, str],
    ref: str | None,
    my_vote: int = 0,
    children: list[CommonsReply] | None = None,
) -> CommonsReply:
    shown = reply.status == "visible"
    mine = ref is not None and reply.author_ref == ref
    if not shown:
        body_html = f"<p>{REMOVED_BODY if reply.status == 'removed' else DELETED_BODY}</p>"
        handle = DELETED_BODY
    elif reply.kind == "bot":
        body_html = render(db, reply.body_md)
        handle = BOT_HANDLE
    else:
        body_html = render(db, reply.body_md)
        handle = DELETED if reply.author_ref is None else handles.get(reply.author_ref, "Anonymous")
    return CommonsReply(
        id=reply.id,
        parent_id=reply.parent_id,
        depth=reply.depth,
        kind="bot" if reply.kind == "bot" else "human",
        handle=handle,
        is_op=shown
        and reply.kind == "human"
        and reply.author_ref is not None
        and reply.author_ref == thread.author_ref,
        is_mine=mine and shown,
        body_html=body_html,
        body_md=reply.body_md if mine and shown else None,
        citations=_citations(reply.citations) if shown and reply.kind == "bot" else [],
        score=reply.score,
        my_vote=my_vote,
        accepted=thread.accepted_reply_id == reply.id,
        status=reply.status,
        created_day=reply.created_day,
        edited_day=reply.edited_day,
        children=children or [],
    )


def _top_order(reply: CommonsReply) -> tuple[int, int, int, int]:
    # The bot's answer first, then the accepted reply, then by score, oldest first.
    return (0 if reply.kind == "bot" else 1, 0 if reply.accepted else 1, -reply.score, reply.id)


def reply_tree(db: Session, thread: m.CommonsThread, viewer: Viewer) -> list[CommonsReply]:
    rows = list(
        db.scalars(
            sa.select(m.CommonsReply)
            .where(m.CommonsReply.thread_id == thread.id)
            .order_by(m.CommonsReply.id)
        )
    )
    ref = viewer.ref(thread.id)
    handles = _handles(db, thread.id)
    votes = _my_votes(db, viewer, "reply", {r.id: ref for r in rows} if ref else {})
    children: dict[int | None, list[m.CommonsReply]] = defaultdict(list)
    for r in rows:
        children[r.parent_id].append(r)

    def build(reply: m.CommonsReply) -> CommonsReply | None:
        kids = [k for k in (build(c) for c in children[reply.id]) if k is not None]
        if reply.status != "visible" and not kids:
            return None  # a tombstone with nothing under it is left out
        return reply_out(
            db,
            reply,
            thread=thread,
            handles=handles,
            ref=ref,
            my_vote=votes.get(reply.id, 0),
            children=kids,
        )

    top = [k for k in (build(r) for r in children[None]) if k is not None]
    return sorted(top, key=_top_order)


def _tombstone(thread: m.CommonsThread) -> CommonsThreadDetail:
    return CommonsThreadDetail(
        id=thread.id,
        title=DELETED_BODY,
        excerpt="",
        score=thread.score,
        reply_count=0,
        answer_count=0,
        answered=False,
        bot_state=thread.bot_state,
        has_bot_answer=False,
        handle="You",
        is_mine=True,
        status=thread.status,
        created_day=thread.created_day,
        edited_day=thread.edited_day,
        body_html="",
    )


def thread_detail(db: Session, viewer: Viewer, thread_id: int) -> CommonsThreadDetail:
    thread = db.get(m.CommonsThread, thread_id)
    if thread is None:
        raise not_found()
    ref = viewer.ref(thread.id)
    if thread.status != "visible":
        if ref is not None and thread.author_ref == ref:
            return _tombstone(thread)
        raise not_found()
    stmt, _, _ = _summary_query()
    row = db.execute(stmt.where(m.CommonsThread.id == thread.id)).one()
    votes = _my_votes(db, viewer, "thread", {thread.id: ref} if ref else {})
    base = _summary(row, viewer=viewer, my_vote=votes.get(thread.id, 0))
    mentions = course_codes_in(db, f"{thread.title}\n{thread.body_md}")
    return CommonsThreadDetail(
        **base,
        body_html=render(db, thread.body_md) if thread.body_md.strip() else "",
        body_md=thread.body_md if base["is_mine"] else None,
        mentions=[CommonsCourse(code=c, title=t) for c, t in mentions.items()],
        following=_following(db, viewer, thread.id),
        accepted_reply_id=thread.accepted_reply_id,
        last_reply_id=thread.last_reply_id,
        replies=reply_tree(db, thread, viewer),
    )


def create_thread(
    db: Session, account: m.Account, body: CommonsThreadCreate
) -> CommonsThreadDetail:
    ensure_can_write(account)
    course = find_course(db, body.course_code) if body.course_code else None
    title = " ".join(scrub(body.title).split())
    thread = m.CommonsThread(
        course_id=course.id if course else None,
        title=title,
        body_md=scrub(body.body_md).strip(),
        tags=body.tags,
        bot_state="pending",
        status="visible",
    )
    db.add(thread)
    db.flush()  # the id is part of the ref
    ref = commons_ref(account.id, thread.id)
    thread.author_ref = ref
    handle_for(db, thread.id, ref)
    db.commit()
    return thread_detail(db, Viewer(account), thread.id)


def update_thread(
    db: Session, account: m.Account, thread_id: int, body: CommonsThreadUpdate
) -> CommonsThreadDetail:
    thread = _own_thread(db, account, thread_id)
    ensure_can_write(account)
    fields = body.model_fields_set
    if "title" in fields and body.title is not None:
        title = " ".join(scrub(body.title).split())
        if len(title) < 8:
            raise HTTPException(status_code=422, detail="The title needs at least 8 characters.")
        thread.title = title
    if "body_md" in fields and body.body_md is not None:
        thread.body_md = scrub(body.body_md).strip()
    if "tags" in fields and body.tags is not None:
        thread.tags = body.tags
    if "course_code" in fields:
        thread.course_id = find_course(db, body.course_code).id if body.course_code else None
    thread.edited_day = today()
    db.commit()
    return thread_detail(db, Viewer(account), thread.id)


def delete_thread(db: Session, account: m.Account, thread_id: int) -> None:
    """Soft delete: the question disappears for everyone; its text is blanked. Replies stay in
    the database for their own authors (export) but are no longer shown."""
    thread = _own_thread(db, account, thread_id)
    thread.status = "deleted"
    thread.title = DELETED_BODY
    thread.body_md = ""
    thread.edited_day = today()
    db.commit()


# ---------------------------------------------------------------------------------- replies


def _count_replies(db: Session, thread_id: int) -> int:
    return int(
        db.scalar(
            sa.select(sa.func.count()).where(
                m.CommonsReply.thread_id == thread_id,
                m.CommonsReply.kind == "human",
                m.CommonsReply.status == "visible",
            )
        )
        or 0
    )


def recount(db: Session, thread: m.CommonsThread) -> None:
    thread.reply_count = _count_replies(db, thread.id)


def place_under(
    db: Session, thread: m.CommonsThread, parent_id: int | None
) -> tuple[int | None, int]:
    """(parent id, depth) of a new reply under `parent_id`; deeper than MAX_DEPTH, the reply
    becomes a sibling of its parent."""
    if parent_id is None:
        return None, 0
    parent = db.get(m.CommonsReply, parent_id)
    if parent is None or parent.thread_id != thread.id:
        raise not_found("Reply")
    if parent.status != "visible":
        raise HTTPException(status_code=409, detail="You can only reply to a visible reply.")
    if parent.depth + 1 > MAX_DEPTH:
        return parent.parent_id, parent.depth
    return parent.id, parent.depth + 1


def create_reply(
    db: Session, account: m.Account, thread_id: int, body: CommonsReplyCreate
) -> CommonsReplyPosted:
    thread = _visible_thread(db, thread_id, lock=True)
    ensure_can_write(account)
    parent_id, depth = place_under(db, thread, body.parent_id)
    ref = commons_ref(account.id, thread.id)
    handle_for(db, thread.id, ref)
    text = scrub(body.body_md).strip()
    reply = m.CommonsReply(
        thread_id=thread.id,
        parent_id=parent_id,
        depth=depth,
        author_ref=ref,
        kind="human",
        body_md=text,
        status="visible",
    )
    db.add(reply)
    db.flush()
    thread.last_reply_id = reply.id
    recount(db, thread)
    db.commit()
    db.refresh(reply)
    out = reply_out(db, reply, thread=thread, handles=_handles(db, thread.id), ref=ref)
    return CommonsReplyPosted(
        reply=out, summon_bot=summons_bot(text), reply_count=thread.reply_count
    )


def _own_reply(
    db: Session, account: m.Account, reply_id: int
) -> tuple[m.CommonsReply, m.CommonsThread, str]:
    reply = db.get(m.CommonsReply, reply_id)
    if reply is None:
        raise not_found("Reply")
    thread = db.get(m.CommonsThread, reply.thread_id)
    assert thread is not None  # FK
    ref = commons_ref(account.id, thread.id)
    if thread.status != "visible" and thread.author_ref != ref:
        raise not_found("Reply")
    if reply.kind == "bot":
        raise HTTPException(status_code=403, detail="The AI's answer cannot be edited.")
    if reply.author_ref != ref:
        if reply.status != "visible":
            raise not_found("Reply")
        raise HTTPException(status_code=403, detail="You can only change your own replies.")
    if reply.status != "visible":
        raise HTTPException(status_code=409, detail="This reply was deleted.")
    return reply, thread, ref


def update_reply(
    db: Session, account: m.Account, reply_id: int, body: CommonsReplyUpdate
) -> CommonsReply:
    reply, thread, ref = _own_reply(db, account, reply_id)
    ensure_can_write(account)
    reply.body_md = scrub(body.body_md).strip()
    reply.edited_day = today()
    db.commit()
    return reply_out(db, reply, thread=thread, handles=_handles(db, thread.id), ref=ref)


def delete_reply(db: Session, account: m.Account, reply_id: int) -> None:
    """Soft delete: the text is blanked and the reply shows as "[deleted]" while replies under
    it remain."""
    reply, thread, _ = _own_reply(db, account, reply_id)
    reply.status = "deleted"
    reply.body_md = ""
    reply.edited_day = today()
    if thread.accepted_reply_id == reply.id:
        thread.accepted_reply_id = None
    recount(db, thread)
    db.commit()


# ------------------------------------------------------------------------------------ votes


def vote(db: Session, account: m.Account, body: CommonsVoteIn) -> CommonsVoteOut:
    model: type[m.CommonsThread] | type[m.CommonsReply]
    if body.target_type == "thread":
        target: m.CommonsThread | m.CommonsReply = _visible_thread(db, body.target_id)
        thread_id = target.id
        model = m.CommonsThread
    else:
        reply = db.get(m.CommonsReply, body.target_id)
        if reply is None or reply.status != "visible":
            raise not_found("Reply")
        _visible_thread(db, reply.thread_id)
        target, thread_id, model = reply, reply.thread_id, m.CommonsReply
    ensure_can_write(account)
    ref = commons_ref(account.id, thread_id)
    if target.author_ref == ref:
        raise HTTPException(status_code=403, detail="You can't vote on your own post.")
    # Serialise votes on one item so the tally below counts every committed vote.
    db.execute(sa.select(model.id).where(model.id == target.id).with_for_update())
    where = (
        m.CommonsVote.voter_ref == ref,
        m.CommonsVote.target_type == body.target_type,
        m.CommonsVote.target_id == target.id,
    )
    if body.value == 0:
        db.execute(sa.delete(m.CommonsVote).where(*where))
    else:
        db.execute(
            insert(m.CommonsVote)
            .values(
                voter_ref=ref, target_type=body.target_type, target_id=target.id, value=body.value
            )
            .on_conflict_do_update(constraint="uq_commons_vote", set_={"value": body.value})
        )
    score = int(
        db.scalar(
            sa.select(sa.func.coalesce(sa.func.sum(m.CommonsVote.value), 0)).where(
                m.CommonsVote.target_type == body.target_type,
                m.CommonsVote.target_id == target.id,
            )
        )
        or 0
    )
    db.execute(sa.update(model).where(model.id == target.id).values(score=score))
    db.commit()
    return CommonsVoteOut(score=score, my_vote=body.value)


# ------------------------------------------------------------------------ accept and follow


def accept(
    db: Session, account: m.Account, thread_id: int, reply_id: int | None
) -> CommonsAcceptOut:
    thread = _visible_thread(db, thread_id)
    if thread.author_ref != commons_ref(account.id, thread.id):
        raise HTTPException(status_code=403, detail="Only the person who asked can accept.")
    ensure_can_write(account)
    if reply_id is not None:
        reply = db.get(m.CommonsReply, reply_id)
        if reply is None or reply.thread_id != thread.id or reply.status != "visible":
            raise not_found("Reply")
    thread.accepted_reply_id = reply_id
    db.commit()
    return CommonsAcceptOut(accepted_reply_id=reply_id)


def follow(db: Session, account: m.Account, thread_id: int, on: bool) -> CommonsFollowOut:
    _visible_thread(db, thread_id)
    profile = db.get(m.StudentProfile, account.id)
    if profile is None:
        profile = m.StudentProfile(account_id=account.id)
        db.add(profile)
        db.flush()
    follows = dict(profile.follows or {})
    threads = [int(t) for t in follows.get("threads", []) if isinstance(t, int)]
    if on and thread_id not in threads:
        threads.append(thread_id)
    if not on:
        threads = [t for t in threads if t != thread_id]
    # A new dict: SQLAlchemy does not see changes made inside a JSONB value.
    profile.follows = {**follows, "threads": threads[-500:]}
    profile.updated_day = today()
    db.commit()
    return CommonsFollowOut(following=on)


# --------------------------------------------------------------------------------- presence


def _typing_index(thread_id: int) -> str:
    return f"commons:typing:{thread_id}"


def _typing_key(thread_id: int, who: str) -> str:
    return f"commons:typing:{thread_id}:{who}"


def typing(db: Session, store: Store, account: m.Account, thread_id: int) -> None:
    """Mark the account as typing on the thread for 8 seconds. Redis holds only a hash of the
    thread ref, never the account id."""
    _visible_thread(db, thread_id)
    who = presence_key(commons_ref(account.id, thread_id))
    store.put(_typing_key(thread_id, who), str(int(time.time())), TYPING_TTL_S)
    store.sadd(_typing_index(thread_id), who, TYPING_TTL_S * 4)


def presence(db: Session, store: Store, viewer: Viewer, thread_id: int) -> CommonsPresence:
    thread = _visible_thread(db, thread_id)
    me = viewer.ref(thread_id)
    mine = presence_key(me) if me else None
    others = 0
    for who in store.smembers(_typing_index(thread_id)):
        if store.get(_typing_key(thread_id, who)) is None:
            store.srem(_typing_index(thread_id), who)
        elif who != mine:
            others += 1
    return CommonsPresence(
        typing=others,
        latest_reply_id=thread.last_reply_id,
        reply_count=thread.reply_count,
        score=thread.score,
        bot_state=thread.bot_state,
    )


# ---------------------------------------------------------------------------------- reports


def report(db: Session, account: m.Account, body: CommonsReportIn) -> CommonsReportOut:
    if body.target_type == "thread":
        thread = db.get(m.CommonsThread, body.target_id)
        if thread is None or thread.status != "visible":
            raise not_found()
        thread_id = thread.id
    else:
        reply = db.get(m.CommonsReply, body.target_id)
        if reply is None or reply.status != "visible":
            raise not_found("Reply")
        _visible_thread(db, reply.thread_id)
        thread_id = reply.thread_id
    ref = commons_ref(account.id, thread_id)
    existing = db.scalar(
        sa.select(m.CommonsReport).where(
            m.CommonsReport.target_type == body.target_type,
            m.CommonsReport.target_id == body.target_id,
            m.CommonsReport.reporter_ref == ref,
            m.CommonsReport.status == "open",
        )
    )
    if existing is not None:
        return CommonsReportOut(id=existing.id, status="open")
    row = m.CommonsReport(
        target_type=body.target_type,
        target_id=body.target_id,
        reason=scrub(body.reason).strip()[:500],
        reporter_ref=ref,
        status="open",
    )
    db.add(row)
    db.commit()
    return CommonsReportOut(id=row.id, status="open")


def thread_refs(db: Session, account_id: uuid.UUID) -> dict[str, int]:
    """{ref: thread id} of the account on every thread (for export and deletion)."""
    ids = db.scalars(sa.select(m.CommonsThread.id)).all()
    return {commons_ref(account_id, tid): tid for tid in ids}
