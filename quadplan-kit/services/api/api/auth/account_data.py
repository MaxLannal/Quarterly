"""Reading an account's plans for export, and erasing an account (SPEC "Account deletion")."""

from __future__ import annotations

import uuid
from typing import Literal

import sqlalchemy as sa
from planner_core.hashing import plan_hash
from planner_core.models import Goal, PlanState
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from api.auth.hashing import author_ref
from api.db import models as m
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


def _plan_state(db: Session, plan: m.Plan) -> PlanState:
    """Rebuild the planner_core PlanState from the `plan*` tables."""
    item_rows = db.execute(
        sa.select(m.PlanItem, m.Course.code)
        .outerjoin(m.Course, m.Course.id == m.PlanItem.course_id)
        .where(m.PlanItem.plan_id == plan.id)
        .order_by(m.PlanItem.id)
    ).all()
    credit_rows = db.execute(
        sa.select(m.Credit, m.Course.code)
        .outerjoin(m.Course, m.Course.id == m.Credit.maps_to_course_id)
        .where(m.Credit.plan_id == plan.id)
        .order_by(m.Credit.id)
    ).all()
    program_rows = db.execute(
        sa.select(m.PlanProgram, m.ProgramVersion.program_id)
        .join(m.ProgramVersion, m.ProgramVersion.id == m.PlanProgram.program_version_id)
        .where(m.PlanProgram.plan_id == plan.id)
        .order_by(m.PlanProgram.id)
    ).all()
    goals = db.scalars(sa.select(m.Goal).where(m.Goal.plan_id == plan.id).order_by(m.Goal.id))
    return PlanState.model_validate(
        {
            "catalog_year": plan.catalog_year,
            "entry_term": plan.entry_term,
            "entry_year_level": plan.entry_year_level,
            "placements": list(plan.placements),
            "overload_reasons": dict(plan.overload_reasons),
            "items": [
                {
                    "id": str(item.id),
                    "course": code,
                    "slot_ref": item.slot_ref,
                    "term": item.term_id,
                    "status": item.status,
                    "locked": item.locked,
                    "units": item.units,
                    "grading": item.grading,
                    "grade": item.grade,
                }
                for item, code in item_rows
            ],
            "credits": [
                {"kind": c.kind, "label": c.label, "maps_to": code, "units": c.units}
                for c, code in credit_rows
            ],
            "programs": [
                {
                    "program_id": program_id,
                    "version_id": pp.program_version_id,
                    "options": pp.options,
                }
                for pp, program_id in program_rows
            ],
            "goals": [
                _GOAL.validate_python(
                    {
                        **g.params,
                        "id": g.goal_key,
                        "type": g.type,
                        "scope": g.scope,
                        "term": g.term_id,
                        "hard": g.hard,
                        "weight": g.weight,
                    }
                )
                for g in goals
            ],
        }
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
    db.delete(account)
