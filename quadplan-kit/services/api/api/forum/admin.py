"""The moderation queue in the curator console (SPEC "Moderation and community rules").

The queue holds every post or comment that is held for review or has an open report. An
admin approves (publish, dismiss the reports) or removes (take down, uphold the reports).
Three upheld removals suspend the author for 30 days.

Forum rows carry no account id, so finding the author of a removed item means recomputing
`author_ref(account, page)` for every account: only the server, which holds the key, can link
an item to an account, and it does so only when a removal is upheld. Nothing about the author
is shown to the moderator except whether the removal triggered a suspension.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from typing import Literal

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.auth.hashing import author_ref
from api.db import models as m
from api.forum.markdown import render_markdown
from api.forum.pseudonyms import DELETED
from api.forum.service import today
from api.schemas.common import Page
from api.schemas.forum import (
    ModerationDecision,
    ModerationItemOut,
    ModerationReport,
    ModerationResult,
)

TargetType = Literal["post", "comment"]
STRIKES_FOR_SUSPENSION = 3
SUSPENSION_DAYS = 30


def require_admin(account: m.Account) -> None:
    if account.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can use the moderation queue.")


def _labels(db: Session, target_type: TargetType, ids: list[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = db.scalars(
        sa.select(m.ModerationAction)
        .where(
            m.ModerationAction.target_type == target_type,
            m.ModerationAction.target_id.in_(ids),
            m.ModerationAction.actor == "model",
        )
        .order_by(m.ModerationAction.id)
    )
    return {row.target_id: row.reason or "" for row in rows}


def queue(db: Session, *, limit: int, offset: int) -> Page[ModerationItemOut]:
    open_reports = db.scalars(
        sa.select(m.Report).where(m.Report.status == "open").order_by(m.Report.id)
    ).all()
    reports: dict[tuple[str, int], list[m.Report]] = defaultdict(list)
    for r in open_reports:
        reports[(r.target_type, r.target_id)].append(r)

    post_ids = set(db.scalars(sa.select(m.Post.id).where(m.Post.status == "held"))) | {
        tid for (tt, tid) in reports if tt == "post"
    }
    comment_ids = set(db.scalars(sa.select(m.Comment.id).where(m.Comment.status == "held"))) | {
        tid for (tt, tid) in reports if tt == "comment"
    }

    comments = (
        db.scalars(sa.select(m.Comment).where(m.Comment.id.in_(comment_ids))).all()
        if comment_ids
        else []
    )
    all_post_ids = post_ids | {c.post_id for c in comments}
    posts = {
        p.id: p
        for p in (
            db.scalars(sa.select(m.Post).where(m.Post.id.in_(all_post_ids))).all()
            if all_post_ids
            else []
        )
    }
    page_ids = {p.course_instructor_id for p in posts.values()}
    page_info = {
        pid: (code, name, slug)
        for pid, code, name, slug in (
            db.execute(
                sa.select(
                    m.CourseInstructor.id,
                    m.Course.code,
                    m.Instructor.display_name,
                    m.Instructor.slug,
                )
                .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
                .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
                .where(m.CourseInstructor.id.in_(page_ids))
            )
            if page_ids
            else []
        )
    }
    pseudonym_ids = {p.pseudonym_id for p in posts.values()} | {c.pseudonym_id for c in comments}
    handles = {
        pid: handle
        for pid, handle in db.execute(
            sa.select(m.Pseudonym.id, m.Pseudonym.handle).where(
                m.Pseudonym.id.in_([i for i in pseudonym_ids if i is not None])
            )
        )
    }
    post_labels = _labels(db, "post", list(post_ids))
    comment_labels = _labels(db, "comment", [c.id for c in comments])

    def report_outs(
        target_type: str, target_id: int, page_id: int, ref: str | None
    ) -> list[ModerationReport]:
        return [
            ModerationReport(
                id=r.id,
                reason=r.reason,
                created_day=r.created_day,
                from_author=ref is not None and r.reporter_ref == ref,
            )
            for r in reports.get((target_type, target_id), [])
        ]

    items: list[ModerationItemOut] = []
    for pid in post_ids:
        p = posts[pid]
        code, name, slug = page_info[p.course_instructor_id]
        items.append(
            ModerationItemOut(
                target_type="post",
                target_id=p.id,
                post_id=p.id,
                page_id=p.course_instructor_id,
                course_code=code,
                instructor_name=name,
                instructor_slug=slug,
                kind=p.kind,
                pseudonym=handles.get(p.pseudonym_id or 0, DELETED),
                title=p.title,
                body_md=p.body_md,
                body_html=render_markdown(p.body_md),
                status=p.status,
                created_day=p.created_day,
                model_label=post_labels.get(p.id),
                reports=report_outs("post", p.id, p.course_instructor_id, p.author_ref),
            )
        )
    for c in comments:
        p = posts[c.post_id]
        code, name, slug = page_info[p.course_instructor_id]
        items.append(
            ModerationItemOut(
                target_type="comment",
                target_id=c.id,
                post_id=p.id,
                page_id=p.course_instructor_id,
                course_code=code,
                instructor_name=name,
                instructor_slug=slug,
                kind="comment",
                pseudonym=handles.get(c.pseudonym_id or 0, DELETED),
                title=None,
                body_md=c.body_md,
                body_html=render_markdown(c.body_md),
                status=c.status,
                created_day=c.created_day,
                model_label=comment_labels.get(c.id),
                reports=report_outs("comment", c.id, p.course_instructor_id, c.author_ref),
            )
        )
    # Oldest first: the queue is worked from the front.
    items.sort(key=lambda i: (i.created_day, i.target_type, i.target_id))
    return Page[ModerationItemOut](
        items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset
    )


def _target(db: Session, target_type: TargetType, target_id: int) -> tuple[m.Post | m.Comment, int]:
    if target_type == "post":
        post = db.get(m.Post, target_id)
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found.")
        return post, post.course_instructor_id
    comment = db.get(m.Comment, target_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found.")
    parent = db.get(m.Post, comment.post_id)
    assert parent is not None
    return comment, parent.course_instructor_id


def _find_account(db: Session, page_id: int, ref: str | None) -> m.Account | None:
    """The account whose ref on `page_id` is `ref` (recomputed with the server key)."""
    if ref is None:
        return None
    for account_id in db.scalars(sa.select(m.Account.id)):
        if author_ref(account_id, page_id) == ref:
            return db.get(m.Account, account_id)
    return None


def upheld_removals(db: Session, account_id: uuid.UUID, since: dt.date | None = None) -> int:
    """Distinct items of this account that an admin removed and that are still removed (a
    removal an admin later reversed is not upheld). `since` counts only removals from that day."""
    query = sa.select(m.ModerationAction.target_type, m.ModerationAction.target_id).where(
        m.ModerationAction.actor == "admin", m.ModerationAction.action == "remove"
    )
    if since is not None:
        query = query.where(m.ModerationAction.created_day >= since)
    removed = db.execute(query.distinct())
    count = 0
    for target_type, target_id in removed:
        if target_type == "post":
            row = db.execute(
                sa.select(m.Post.course_instructor_id, m.Post.author_ref).where(
                    m.Post.id == target_id, m.Post.status == "removed"
                )
            ).first()
        else:
            row = db.execute(
                sa.select(m.Post.course_instructor_id, m.Comment.author_ref)
                .join(m.Post, m.Post.id == m.Comment.post_id)
                .where(m.Comment.id == target_id, m.Comment.status == "removed")
            ).first()
        if row is not None and row[1] is not None and author_ref(account_id, row[0]) == row[1]:
            count += 1
    return count


def decide(
    db: Session,
    admin: m.Account,
    target_type: TargetType,
    target_id: int,
    body: ModerationDecision,
) -> ModerationResult:
    target, page_id = _target(db, target_type, target_id)
    already_removed = target.status == "removed" and bool(
        db.scalar(
            sa.select(
                sa.exists().where(
                    m.ModerationAction.target_type == target_type,
                    m.ModerationAction.target_id == target_id,
                    m.ModerationAction.actor == "admin",
                    m.ModerationAction.action == "remove",
                )
            )
        )
    )
    approve = body.decision == "approve"
    target.status = "visible" if approve else "removed"
    db.execute(
        sa.update(m.Report)
        .where(
            m.Report.target_type == target_type,
            m.Report.target_id == target_id,
            m.Report.status == "open",
        )
        .values(status="dismissed" if approve else "upheld")
    )
    db.add(
        m.ModerationAction(
            target_type=target_type,
            target_id=target_id,
            action="approve" if approve else "remove",
            reason=body.note,
            actor="admin",
            actor_account_id=admin.id,
        )
    )
    db.flush()
    suspended = False
    if not approve and not already_removed:
        author = _find_account(db, page_id, target.author_ref)
        if author is not None:
            strikes = upheld_removals(db, author.id)
            if strikes and strikes % STRIKES_FOR_SUSPENSION == 0:
                author.suspended_until = today() + dt.timedelta(days=SUSPENSION_DAYS)
                suspended = True
    db.commit()
    return ModerationResult(
        target_type=target_type,
        target_id=target_id,
        status=target.status,
        author_suspended=suspended,
    )
