"""The moderation queue in the curator console (SPEC "Moderation and community rules").

Posts are published without a check (P08-1), so the queue holds what students report (and
any item an earlier version of the forum held). An admin approves (keep it, dismiss the
reports) or removes (take it down, uphold the reports). When removing, the admin may also
suspend the author for a number of days; suspensions are never automatic (P08-3).

Forum rows carry no account id, so finding the author of a removed item means recomputing
`author_ref(account, page)` for every account: only the server, which holds the key, can link
an item to an account, and it does so only when an admin asks for a suspension. Nothing about
the author is shown to the moderator except whether the suspension was applied.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from typing import Literal

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.attributes.records import forget_extractions
from api.auth.hashing import author_ref
from api.db import models as m
from api.forum.markdown import render_markdown
from api.forum.pseudonyms import DELETED
from api.forum.service import _latest_actions, today
from api.schemas.common import Page
from api.schemas.forum import (
    EndSuspensionResult,
    ModerationDecision,
    ModerationItemOut,
    ModerationReport,
    ModerationResult,
    SuspensionOut,
)

TargetType = Literal["post", "comment"]


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
    """Distinct items of this account that an admin removed and that are still removed by that
    admin: the item's latest moderation action is the admin's removal (a removal an admin later
    reversed is not upheld, and an older admin removal does not count again when the automatic
    check removes the item later). `since` counts only removals from that day."""
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
        kind: TargetType = "post" if target_type == "post" else "comment"
        latest = _latest_actions(db, kind, [target_id]).get(target_id)
        upheld = latest is not None and latest.actor == "admin" and latest.action == "remove"
        if (
            upheld
            and row is not None
            and row[1] is not None
            and author_ref(account_id, row[0]) == row[1]
        ):
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
    approve = body.decision == "approve"
    if approve and body.suspend_days is not None:
        raise HTTPException(
            status_code=422, detail="A suspension goes with removing the post or comment."
        )
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
    reason = body.note
    if body.suspend_days is not None:  # the length is kept with the decision that set it
        reason = f"{body.note or ''} [author suspended {body.suspend_days} days]".strip()
    db.add(
        m.ModerationAction(
            target_type=target_type,
            target_id=target_id,
            action="approve" if approve else "remove",
            reason=reason,
            actor="admin",
            actor_account_id=admin.id,
        )
    )
    if not approve and target_type == "post":
        # Nothing derived from a removed post may outlive it: its extracted quotes, and the
        # page's "What students say" (which may draw on it without citing it).
        forget_extractions(db, [target_id])
        db.execute(sa.delete(m.ForumSummary).where(m.ForumSummary.course_instructor_id == page_id))
    db.flush()
    suspended = False
    if body.suspend_days is not None:
        author = _find_account(db, page_id, target.author_ref)
        if author is not None:  # None: the author deleted their account
            until = today() + dt.timedelta(days=body.suspend_days)
            if author.suspended_until is None or author.suspended_until < until:
                author.suspended_until = until
            suspended = True
    db.commit()
    return ModerationResult(
        target_type=target_type,
        target_id=target_id,
        status=target.status,
        author_suspended=suspended,
    )


# ------------------------------------------------------------------ ending a suspension early


def _page_label(db: Session, page_id: int) -> tuple[str, str]:
    row = db.execute(
        sa.select(m.Course.code, m.Instructor.display_name)
        .join(m.CourseInstructor, m.CourseInstructor.course_id == m.Course.id)
        .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        .where(m.CourseInstructor.id == page_id)
    ).one()
    return str(row[0]), str(row[1])


def suspensions(db: Session) -> list[SuspensionOut]:
    """Active suspensions, each shown by the latest removal that started it. Authors are found
    by recomputing refs on the server and are never shown; one row per author, so two rows
    never reveal a shared author."""
    actions = db.scalars(
        sa.select(m.ModerationAction)
        .where(
            m.ModerationAction.actor == "admin",
            m.ModerationAction.action == "remove",
            m.ModerationAction.reason.like("%[author suspended %"),
        )
        .order_by(m.ModerationAction.id.desc())
    ).all()
    seen: set[uuid.UUID] = set()
    out: list[SuspensionOut] = []
    for action in actions:
        target_type: TargetType = "post" if action.target_type == "post" else "comment"
        try:
            target, page_id = _target(db, target_type, action.target_id)
        except HTTPException:
            continue  # deleted since
        author = _find_account(db, page_id, target.author_ref)
        if author is None or author.id in seen:
            continue
        seen.add(author.id)
        if author.suspended_until is None or author.suspended_until <= today():
            continue
        code, name = _page_label(db, page_id)
        out.append(
            SuspensionOut(
                target_type=target_type,
                target_id=action.target_id,
                course_code=code,
                instructor_name=name,
                title=target.title if isinstance(target, m.Post) else None,
                excerpt=target.body_md[:120],
                removed_day=action.created_day,
                until=author.suspended_until,
            )
        )
    return out


def end_suspension(
    db: Session, admin: m.Account, target_type: TargetType, target_id: int
) -> EndSuspensionResult:
    """Lift the suspension of the author of this removed item (P08-14, FEEDBACK "End
    suspension")."""
    target, page_id = _target(db, target_type, target_id)
    author = _find_account(db, page_id, target.author_ref)
    if author is None or author.suspended_until is None or author.suspended_until <= today():
        raise HTTPException(status_code=404, detail="No active suspension for this item.")
    author.suspended_until = None
    db.add(
        m.ModerationAction(
            target_type=target_type,
            target_id=target_id,
            action="unsuspend",
            reason="suspension ended early",
            actor="admin",
            actor_account_id=admin.id,
        )
    )
    db.commit()
    return EndSuspensionResult(target_type=target_type, target_id=target_id, ended=True)
