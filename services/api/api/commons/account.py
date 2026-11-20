"""The Commons in account export and deletion (SPEC "Account deletion", like the forum's posts in
`api.auth.account_data`). The lead wires these into the account endpoints.

Commons rows carry no account id, only `commons_ref(account_id, thread_id)`, so the account's
refs are recomputed for every thread.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session, aliased

from api.commons.service import thread_refs
from api.db import models as m


def export_commons(db: Session, account_id: uuid.UUID) -> dict[str, Any]:
    """Everything the account wrote or did in the Commons: questions, replies, votes and
    reports (followed threads are in the profile export). Day-level dates only."""
    refs = thread_refs(db, account_id)
    if not refs:
        return {"threads": [], "replies": [], "votes": [], "reports": []}
    mine = list(refs)
    course_code = (
        sa.select(m.Course.code).where(m.Course.id == m.CommonsThread.course_id).scalar_subquery()
    )
    threads = [
        {
            "id": t.id,
            "title": t.title,
            "body_md": t.body_md,
            "course": code,
            "tags": list(t.tags or []),
            "status": t.status,
            "created_day": t.created_day.isoformat(),
            "edited_day": t.edited_day.isoformat() if t.edited_day else None,
        }
        for t, code in db.execute(
            sa.select(m.CommonsThread, course_code)
            .where(m.CommonsThread.author_ref.in_(mine))
            .order_by(m.CommonsThread.id)
        )
    ]
    replies = [
        {
            "id": r.id,
            "thread_id": r.thread_id,
            "parent_id": r.parent_id,
            "body_md": r.body_md,
            "status": r.status,
            "created_day": r.created_day.isoformat(),
            "edited_day": r.edited_day.isoformat() if r.edited_day else None,
        }
        for r in db.scalars(
            sa.select(m.CommonsReply)
            .where(m.CommonsReply.author_ref.in_(mine))
            .order_by(m.CommonsReply.id)
        )
    ]
    votes = [
        {"target_type": v.target_type, "target_id": v.target_id, "value": v.value}
        for v in db.scalars(
            sa.select(m.CommonsVote)
            .where(m.CommonsVote.voter_ref.in_(mine))
            .order_by(m.CommonsVote.id)
        )
    ]
    reports = [
        {
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "status": r.status,
            "created_day": r.created_day.isoformat(),
        }
        for r in db.scalars(
            sa.select(m.CommonsReport)
            .where(m.CommonsReport.reporter_ref.in_(mine))
            .order_by(m.CommonsReport.id)
        )
    ]
    return {"threads": threads, "replies": replies, "votes": votes, "reports": reports}


def _recount(db: Session, thread_ids: set[int]) -> None:
    for thread_id in thread_ids:
        n = db.scalar(
            sa.select(sa.func.count()).where(
                m.CommonsReply.thread_id == thread_id,
                m.CommonsReply.kind == "human",
                m.CommonsReply.status == "visible",
            )
        )
        db.execute(
            sa.update(m.CommonsThread)
            .where(m.CommonsThread.id == thread_id)
            .values(reply_count=int(n or 0))
        )
    if thread_ids:
        # An accepted reply that is gone or blanked is no longer accepted.
        reply = aliased(m.CommonsReply)
        db.execute(
            sa.update(m.CommonsThread)
            .where(
                m.CommonsThread.id.in_(thread_ids),
                m.CommonsThread.accepted_reply_id.is_not(None),
                ~sa.exists().where(
                    reply.id == m.CommonsThread.accepted_reply_id, reply.status == "visible"
                ),
            )
            .values(accepted_reply_id=None)
        )


def forget_commons(db: Session, account_id: uuid.UUID, mode: Literal["delete", "keep"]) -> None:
    """Erase what ties Commons content to the account (the caller commits).

    - mode="keep": questions and replies stay, shown as "[deleted account]" (`author_ref` set
      to NULL).
    - mode="delete": the account's questions go (with every reply under them, their votes and
      reports). Its replies on other questions go too, unless someone replied to them: then the
      reply is blanked, marked deleted and anonymised so the replies under it survive.
    Either way the account's handles and votes are removed (tallied scores stay as they are)
    and its reports lose their reporter ref.
    """
    refs = list(thread_refs(db, account_id))
    if not refs:
        return
    mine_thread = m.CommonsThread.author_ref.in_(refs)
    mine_reply = m.CommonsReply.author_ref.in_(refs)
    touched = set(db.scalars(sa.select(m.CommonsReply.thread_id).where(mine_reply)).all())
    if mode == "delete":
        own_threads = list(db.scalars(sa.select(m.CommonsThread.id).where(mine_thread)))
        if own_threads:
            under = list(
                db.scalars(
                    sa.select(m.CommonsReply.id).where(m.CommonsReply.thread_id.in_(own_threads))
                )
            )
            for target_type, ids in (("thread", own_threads), ("reply", under)):
                if ids:
                    db.execute(
                        sa.delete(m.CommonsVote).where(
                            m.CommonsVote.target_type == target_type,
                            m.CommonsVote.target_id.in_(ids),
                        )
                    )
                    db.execute(
                        sa.delete(m.CommonsReport).where(
                            m.CommonsReport.target_type == target_type,
                            m.CommonsReport.target_id.in_(ids),
                        )
                    )
            # Replies and handles follow by cascade.
            db.execute(sa.delete(m.CommonsThread).where(m.CommonsThread.id.in_(own_threads)))
        touched -= set(own_threads)
        child = aliased(m.CommonsReply)
        has_child = sa.exists().where(child.parent_id == m.CommonsReply.id)
        # Leaves first, repeatedly: a chain of the account's own replies unwinds fully.
        while True:
            leaves = list(db.scalars(sa.select(m.CommonsReply.id).where(mine_reply, ~has_child)))
            if not leaves:
                break
            for model in (m.CommonsVote, m.CommonsReport):
                db.execute(
                    sa.delete(model).where(
                        model.target_type == "reply", model.target_id.in_(leaves)
                    )
                )
            db.execute(sa.delete(m.CommonsReply).where(m.CommonsReply.id.in_(leaves)))
        db.execute(
            sa.update(m.CommonsReply)
            .where(mine_reply)
            .values(author_ref=None, body_md="", status="deleted")
        )
    else:
        db.execute(sa.update(m.CommonsThread).where(mine_thread).values(author_ref=None))
        db.execute(sa.update(m.CommonsReply).where(mine_reply).values(author_ref=None))
    db.execute(sa.delete(m.CommonsVote).where(m.CommonsVote.voter_ref.in_(refs)))
    db.execute(
        sa.update(m.CommonsReport)
        .where(m.CommonsReport.reporter_ref.in_(refs))
        .values(reporter_ref=None)
    )
    db.execute(sa.delete(m.CommonsPseudonym).where(m.CommonsPseudonym.author_ref.in_(refs)))
    _recount(db, touched)


__all__ = ["export_commons", "forget_commons"]
