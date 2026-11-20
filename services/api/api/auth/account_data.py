"""Reading an account's plans for export, and erasing an account (SPEC "Account deletion")."""

from __future__ import annotations

import uuid
from typing import Literal

import sqlalchemy as sa
from planner_core.hashing import plan_hash
from planner_core.models import Goal
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from api.attributes.records import forget_extractions
from api.auth.hashing import author_ref
from api.db import models as m
from api.repo.plans import read_state as _plan_state
from api.schemas.auth import AccountOut
from api.schemas.plans import PlanOut

_GOAL = TypeAdapter[Goal](Goal)


def account_out(account: m.Account) -> AccountOut:
    return AccountOut(
        id=account.id,
        username=account.username,
        role=account.role,
        created_day=account.created_day,
    )


def export_plans(db: Session, account_id: uuid.UUID) -> list[PlanOut]:
    plans = db.scalars(
        sa.select(m.Plan).where(m.Plan.account_id == account_id).order_by(m.Plan.created_day)
    ).all()
    out = []
    for plan in plans:
        state = _plan_state(db, plan)
        out.append(
            PlanOut(
                id=plan.id,
                name=plan.name,
                catalog_year=plan.catalog_year,
                entry_term=plan.entry_term,
                is_primary=plan.is_primary,
                updated_day=plan.updated_day,
                state=state,
                plan_hash=plan_hash(state),
            )
        )
    return out


def delete_account(db: Session, account: m.Account, posts: Literal["delete", "keep"]) -> None:
    """Remove the account row (and with it the email), its plans (FK cascade) and every forum
    row that could tie content to it. The caller commits and ends the sessions.

    Forum rows carry no account id, only `author_ref = HMAC(server_key, account_id || page_id)`,
    so the account's refs are recomputed for every forum page.

    - posts="keep": posts and comments stay, shown as "[deleted account]" (`author_ref` and the
      pseudonym set to NULL).
    - posts="delete": the posts go (with their ratings and comment threads). The account's
      comments on other people's posts go too, unless someone replied: then the comment is
      blanked and anonymised so the replies survive.
    Either way the account's pseudonyms and vote rows are removed (tallied scores are left as
    they are) and its abuse reports lose their reporter ref.
    """
    page_ids = db.scalars(sa.select(m.CourseInstructor.id)).all()
    refs = [author_ref(account.id, page_id) for page_id in page_ids]
    if refs:
        mine_post = m.Post.author_ref.in_(refs)
        mine_comment = m.Comment.author_ref.in_(refs)
        if posts == "delete":
            forget_extractions(db, db.scalars(sa.select(m.Post.id).where(mine_post)).all())
            db.execute(sa.delete(m.Post).where(mine_post))
            reply = sa.orm.aliased(m.Comment)
            has_reply = sa.exists().where(reply.parent_id == m.Comment.id)
            # Leaves first, repeatedly: a chain of the account's own comments unwinds fully.
            while db.execute(  # type: ignore[attr-defined]
                sa.delete(m.Comment).where(mine_comment, ~has_reply)
            ).rowcount:
                pass
            db.execute(
                sa.update(m.Comment)
                .where(mine_comment)
                .values(author_ref=None, pseudonym_id=None, body_md="[deleted]")
            )
        else:
            db.execute(
                sa.update(m.Post).where(mine_post).values(author_ref=None, pseudonym_id=None)
            )
            db.execute(
                sa.update(m.Comment).where(mine_comment).values(author_ref=None, pseudonym_id=None)
            )
        db.execute(sa.delete(m.Vote).where(m.Vote.voter_ref.in_(refs)))
        db.execute(
            sa.update(m.Report).where(m.Report.reporter_ref.in_(refs)).values(reporter_ref=None)
        )
        db.execute(sa.delete(m.Pseudonym).where(m.Pseudonym.author_ref.in_(refs)))
    from api.agents.chat import forget_chats
    from api.commons.account import forget_commons

    forget_chats(db, list(db.scalars(sa.select(m.Plan.id).where(m.Plan.account_id == account.id))))
    # The Commons uses its own per-thread refs; the profile and routes go by FK cascade.
    forget_commons(db, account.id, posts)
    db.delete(account)
