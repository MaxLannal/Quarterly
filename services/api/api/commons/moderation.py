"""Moderating the Commons (OPEN_QUESTIONS CC-7): the admin's queue of reported questions and replies
and the decision on each. Like the forum's queue (`api.forum.admin`), but for Commons items:
remove (the item shows "[removed]" and its children stay) or keep; either way the open reports on
it close and the decision is recorded as a `moderation_action` (no account id of the author is
ever looked up: the author is only a per-thread ref)."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Literal

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.commons.service import excerpt
from api.db import models as m
from api.schemas.commons import (
    CommonsModerationDecision,
    CommonsModerationItem,
    CommonsModerationReport,
    CommonsModerationResult,
)

TargetType = Literal["thread", "reply"]
#: `moderation_action.target_type` for Commons items (the forum uses post / comment).
ACTION_TYPE: dict[str, str] = {"thread": "commons_thread", "reply": "commons_reply"}


def queue(db: Session, *, limit: int = 100) -> list[CommonsModerationItem]:
    """Every Commons item with an open report, oldest report first."""
    reports = db.scalars(
        sa.select(m.CommonsReport)
        .where(m.CommonsReport.status == "open")
        .order_by(m.CommonsReport.id)
    ).all()
    grouped: dict[tuple[str, int], list[m.CommonsReport]] = defaultdict(list)
    for r in reports:
        grouped[(r.target_type, r.target_id)].append(r)
    items: list[CommonsModerationItem] = []
    for (kind, target_id), rows in list(grouped.items())[:limit]:
        thread: m.CommonsThread | None
        if kind == "thread":
            thread = db.get(m.CommonsThread, target_id)
            if thread is None:
                continue
            body, status, title = thread.body_md, thread.status, thread.title
            href = f"/forum/t/{thread.id}"
            bot = False
        else:
            reply = db.get(m.CommonsReply, target_id)
            if reply is None:
                continue
            thread = db.get(m.CommonsThread, reply.thread_id)
            body, status = reply.body_md, reply.status
            title = f"Reply on: {thread.title}" if thread else "Reply"
            href = f"/forum/t/{reply.thread_id}#reply-{reply.id}"
            bot = reply.kind == "bot"
        course = db.get(m.Course, thread.course_id) if thread and thread.course_id else None
        items.append(
            CommonsModerationItem(
                target_type="thread" if kind == "thread" else "reply",
                target_id=target_id,
                title=title,
                excerpt=excerpt(body, 400),
                status=status if status in ("visible", "removed", "deleted") else "visible",
                by_ai=bot,
                course_code=course.code if course else None,
                href=href,
                reports=[
                    CommonsModerationReport(reason=r.reason, created_day=r.created_day)
                    for r in rows
                ],
            )
        )
    return items


def decide(
    db: Session,
    admin: m.Account,
    target_type: TargetType,
    target_id: int,
    body: CommonsModerationDecision,
) -> CommonsModerationResult:
    target: m.CommonsThread | m.CommonsReply | None = (
        db.get(m.CommonsThread, target_id)
        if target_type == "thread"
        else db.get(m.CommonsReply, target_id)
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Not found.")
    if body.decision == "remove" and target.status == "visible":
        target.status = "removed"
    elif body.decision == "keep" and target.status == "removed":
        target.status = "visible"  # an earlier removal undone
    closed = db.execute(
        sa.update(m.CommonsReport)
        .where(
            m.CommonsReport.target_type == target_type,
            m.CommonsReport.target_id == target_id,
            m.CommonsReport.status == "open",
        )
        .values(status="closed")
    )
    db.add(
        m.ModerationAction(
            target_type=ACTION_TYPE[target_type],
            target_id=target_id,
            action="remove" if body.decision == "remove" else "keep",
            reason=(body.note or None),
            actor="admin",
            actor_account_id=admin.id,
            created_day=dt.date.today(),
        )
    )
    db.commit()
    return CommonsModerationResult(
        target_type=target_type,
        target_id=target_id,
        status="removed" if target.status == "removed" else "visible",
        reports_closed=int(getattr(closed, "rowcount", 0) or 0),
    )
