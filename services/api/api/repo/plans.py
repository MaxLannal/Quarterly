"""Saved plans: Postgres rows <-> planner_core `PlanState`, and change sets (SPEC "Plans and
goals"). Day-level dates only. Every function takes an already authorised plan row; the
router checks ownership with `owned_plan`.

Credits and taken courses belong to the student record (Issue #14), not to one plan: every
saved plan reads them from `student_credit` and `student_course`, and saving a plan writes
them back there. A taken course appears in the plan as a completed or in-progress item with
the id `t<student_course.id>`. The old per-plan copies (`credit`, and `plan_item` rows with
those statuses, left by migration 0005) are ignored when read and removed on the next save."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import sqlalchemy as sa
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.hashing import plan_hash
from planner_core.models import ChangeOp, ChangeSet, Goal, PlanState, Report
from planner_core.terms import term_key
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from api.db import models as m
from api.schemas.plans import PlanOut, PlanSummary

_GOAL = TypeAdapter[Goal](Goal)
_OPS = TypeAdapter[list[ChangeOp]](list[ChangeOp])


class PlanNotFoundError(Exception):
    """No such plan, or not this account's (the API answers 404 either way)."""


class InvalidPlanError(Exception):
    """The state names courses or programs the catalog year does not have."""


#: Item statuses kept in the student record (`student_course`) instead of the plan.
TAKEN = frozenset({"completed", "in_progress"})
_TAKEN_PREFIX = "t"


class StalePlanError(Exception):
    """The plan changed since the client (or the change set) last saw it."""

    def __init__(self, current_hash: str) -> None:
        super().__init__(current_hash)
        self.current_hash = current_hash


def owned_plan(db: Session, account_id: uuid.UUID, plan_id: uuid.UUID) -> m.Plan:
    plan = db.get(m.Plan, plan_id)
    if plan is None or plan.account_id != account_id:
        raise PlanNotFoundError(str(plan_id))
    return plan


def read_state(db: Session, plan: m.Plan) -> PlanState:
    """Rebuild the planner_core PlanState from the `plan*` tables."""
    item_rows = db.execute(
        sa.select(m.PlanItem, m.Course.code)
        .outerjoin(m.Course, m.Course.id == m.PlanItem.course_id)
        .where(m.PlanItem.plan_id == plan.id)
        .order_by(m.PlanItem.id)
    ).all()
    taken_rows = db.execute(
        sa.select(m.StudentCourse, m.Course.code)
        .join(m.Course, m.Course.id == m.StudentCourse.course_id)
        .where(m.StudentCourse.account_id == plan.account_id)
        .order_by(m.StudentCourse.id)
    ).all()
    credit_rows = db.execute(
        sa.select(m.StudentCredit, m.Course.code)
        .outerjoin(m.Course, m.Course.id == m.StudentCredit.maps_to_course_id)
        .where(m.StudentCredit.account_id == plan.account_id)
        .order_by(m.StudentCredit.id)
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
            "graduation_term": plan.graduation_term,
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
                # The old per-plan copies of taken courses: the record has them now.
                if not (item.status in TAKEN and item.course_id is not None)
            ]
            + [
                {
                    "id": f"{_TAKEN_PREFIX}{taken.id}",
                    "course": code,
                    "slot_ref": None,
                    "term": taken.term_id,
                    "status": taken.status,
                    "locked": taken.locked,
                    "units": taken.units,
                    "grading": taken.grading,
                    "grade": taken.grade,
                }
                for taken, code in taken_rows
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


def _course_ids(db: Session, year: str, codes: set[str]) -> dict[str, int]:
    if not codes:
        return {}
    rows = db.execute(
        sa.select(m.Course.code, m.Course.id).where(
            m.Course.catalog_year == year, m.Course.code.in_(codes)
        )
    ).all()
    found = {code: course_id for code, course_id in rows}
    unknown = sorted(codes - set(found))
    if unknown:
        raise InvalidPlanError(f"Unknown course(s) for {year}: {', '.join(unknown)}")
    return found


def _version_ids(db: Session, state: PlanState, show_unpublished: bool) -> list[int]:
    wanted = [p.program_id for p in state.programs]
    rows = db.execute(
        sa.select(m.ProgramVersion.program_id, m.ProgramVersion.id, m.ProgramVersion.status).where(
            m.ProgramVersion.catalog_year == state.catalog_year,
            m.ProgramVersion.program_id.in_(wanted),
        )
    ).all()
    found = {pid: vid for pid, vid, status in rows if status == "published" or show_unpublished}
    unknown = [p for p in wanted if p not in found]
    if unknown:
        raise InvalidPlanError(
            f"Unknown program(s) for {state.catalog_year}: {', '.join(sorted(unknown))}"
        )
    return [found[p.program_id] if p.version_id is None else p.version_id for p in state.programs]


def _is_taken(item: Any) -> bool:
    return item.status in TAKEN and item.course is not None


def record_has_data(db: Session, account_id: uuid.UUID) -> bool:
    """Whether the student record already has credits or taken courses."""
    for table in (m.StudentCredit, m.StudentCourse):
        found = db.scalar(sa.select(table.id).where(table.account_id == account_id).limit(1))
        if found is not None:
            return True
    return False


def write_state(
    db: Session,
    plan: m.Plan,
    state: PlanState,
    *,
    show_unpublished: bool,
    items: bool = True,
    record: bool = True,
) -> None:
    """Replace the plan's rows with `state` (its items too unless `items` is False). Its
    credits and taken courses go to the student record, unless `record` is False (a new plan
    when the record already has some: the record wins)."""
    if db.get(m.CatalogYear, state.catalog_year) is None:
        raise InvalidPlanError(f"Unknown catalog year: {state.catalog_year}")
    codes = {c.maps_to for c in state.credits if c.maps_to}
    if items:
        codes |= {i.course for i in state.items if i.course}
    ids = _course_ids(db, state.catalog_year, codes)
    versions = _version_ids(db, state, show_unpublished)
    plan.catalog_year = state.catalog_year
    plan.entry_term = state.entry_term
    plan.entry_year_level = state.entry_year_level
    plan.graduation_term = state.graduation_term
    plan.placements = list(state.placements)
    plan.overload_reasons = dict(state.overload_reasons)
    plan.updated_day = dt.date.today()
    # `credit` rows are the old per-plan copies (migration 0005): removed, never written.
    for table in (m.Credit, m.Goal, m.PlanProgram):
        db.execute(sa.delete(table).where(table.plan_id == plan.id))
    if items:
        _write_items(db, plan, state, ids)
        if record:
            taken = [i for i in state.items if _is_taken(i)]
            _write_taken(db, plan.account_id, taken, ids, state.entry_term)
    if record:
        db.execute(sa.delete(m.StudentCredit).where(m.StudentCredit.account_id == plan.account_id))
        db.add_all(
            m.StudentCredit(
                account_id=plan.account_id,
                kind=c.kind,
                label=c.label,
                maps_to_course_id=ids[c.maps_to] if c.maps_to else None,
                units=c.units,
            )
            for c in state.credits
        )
    db.add_all(
        m.PlanProgram(plan_id=plan.id, program_version_id=vid, options=p.options)
        for p, vid in zip(state.programs, versions, strict=True)
    )
    for goal in state.goals:
        data = goal.model_dump(mode="json", by_alias=True)
        common = {k: data.pop(k) for k in ("id", "type", "scope", "term", "hard", "weight")}
        db.add(
            m.Goal(
                plan_id=plan.id,
                goal_key=common["id"],
                scope=common["scope"],
                term_id=common["term"],
                type=common["type"],
                params=data,
                hard=common["hard"],
                weight=common["weight"],
            )
        )
    db.flush()


def _write_items(db: Session, plan: m.Plan, state: PlanState, ids: dict[str, int]) -> None:
    """Update items in place, keeping their ids (change sets and the UI refer to them), insert
    new ones and delete the rest."""
    rows = {
        str(row.id): row
        for row in db.scalars(sa.select(m.PlanItem).where(m.PlanItem.plan_id == plan.id))
    }
    kept: set[str] = set()
    for item in state.items:
        if _is_taken(item):
            continue  # the student record keeps it (`_write_taken`)
        values = {
            "course_id": ids[item.course] if item.course else None,
            "slot_ref": item.slot_ref,
            "term_id": item.term,
            "status": item.status,
            "locked": item.locked,
            "units": item.units,
            "grading": item.grading,
            "grade": item.grade,
        }
        row = rows.get(item.id) if item.id is not None and item.id not in kept else None
        if row is None:
            db.add(m.PlanItem(plan_id=plan.id, **values))
            continue
        kept.add(str(row.id))
        for key, value in values.items():
            setattr(row, key, value)
    for key, row in rows.items():
        if key not in kept:
            db.delete(row)


def _write_taken(
    db: Session, account_id: uuid.UUID, taken: list[Any], ids: dict[str, int], entry_term: str
) -> None:
    """Make the record's taken courses `taken`, updating rows in place (`t<id>` items) so their
    ids stay stable, inserting new ones and deleting the rest. Courses before the plan's first
    quarter are kept: the plan cannot show them, so leaving them out is not a deletion."""
    rows = {
        f"{_TAKEN_PREFIX}{row.id}": row
        for row in db.scalars(
            sa.select(m.StudentCourse).where(m.StudentCourse.account_id == account_id)
        )
    }
    kept: set[str] = set()
    seen: set[tuple[int, str]] = set()
    for item in taken:
        course_term = (ids[item.course], item.term)
        if course_term in seen:
            continue
        seen.add(course_term)
        values = {
            "course_id": ids[item.course],
            "term_id": item.term,
            "status": item.status,
            "locked": item.locked,
            "units": item.units,
            "grading": item.grading,
            "grade": item.grade,
        }
        row = rows.get(item.id) if item.id is not None and item.id not in kept else None
        if row is None:
            db.add(m.StudentCourse(account_id=account_id, **values))
            continue
        kept.add(item.id)
        for name, value in values.items():
            setattr(row, name, value)
    first = term_key(entry_term)
    for key, row in rows.items():
        if key not in kept and term_key(row.term_id) >= first:
            db.delete(row)


def summary(plan: m.Plan) -> PlanSummary:
    return PlanSummary(
        id=plan.id,
        name=plan.name,
        catalog_year=plan.catalog_year,
        entry_term=plan.entry_term,
        is_primary=plan.is_primary,
        updated_day=plan.updated_day,
    )


def plan_out(db: Session, plan: m.Plan, report: Report | None = None) -> PlanOut:
    state = read_state(db, plan)
    return PlanOut(
        **summary(plan).model_dump(), state=state, plan_hash=plan_hash(state), report=report
    )


def list_plans(db: Session, account_id: uuid.UUID) -> list[PlanSummary]:
    plans = db.scalars(
        sa.select(m.Plan)
        .where(m.Plan.account_id == account_id)
        .order_by(m.Plan.is_primary.desc(), m.Plan.updated_day.desc(), m.Plan.name)
    )
    return [summary(p) for p in plans]


def _make_primary(db: Session, plan: m.Plan) -> None:
    db.execute(
        sa.update(m.Plan)
        .where(m.Plan.account_id == plan.account_id, m.Plan.id != plan.id)
        .values(is_primary=False)
    )
    plan.is_primary = True


def create_plan(
    db: Session,
    account_id: uuid.UUID,
    name: str,
    state: PlanState,
    *,
    is_primary: bool,
    show_unpublished: bool,
) -> m.Plan:
    first = (
        db.scalar(
            sa.select(sa.func.count()).select_from(m.Plan).where(m.Plan.account_id == account_id)
        )
        == 0
    )
    if db.get(m.CatalogYear, state.catalog_year) is None:
        raise InvalidPlanError(f"Unknown catalog year: {state.catalog_year}")
    # A new plan (an import from this browser, a copy) never overwrites a record that already
    # has credits or taken courses (Issue #14 step 15): the plan shows the record's.
    record = not record_has_data(db, account_id)
    plan = m.Plan(
        account_id=account_id,
        name=name,
        catalog_year=state.catalog_year,
        entry_term=state.entry_term,
        is_primary=False,
        created_day=dt.date.today(),
        updated_day=dt.date.today(),
    )
    db.add(plan)
    db.flush()
    write_state(db, plan, state, show_unpublished=show_unpublished, record=record)
    if is_primary or first:
        _make_primary(db, plan)
    return plan


def update_plan(
    db: Session,
    plan: m.Plan,
    *,
    name: str | None,
    is_primary: bool | None,
    state: PlanState | None,
    show_unpublished: bool,
) -> None:
    if name is not None:
        plan.name = name
    if is_primary:
        _make_primary(db, plan)
    elif is_primary is False:
        plan.is_primary = False
    if state is not None:
        if state.catalog_year != plan.catalog_year:
            raise InvalidPlanError("Moving a plan to another catalog year is a separate action.")
        write_state(db, plan, state, show_unpublished=show_unpublished)
    plan.updated_day = dt.date.today()


def duplicate_plan(db: Session, plan: m.Plan, *, show_unpublished: bool) -> m.Plan:
    state = read_state(db, plan)
    copy = state.model_copy(
        update={"items": [i.model_copy(update={"id": None}) for i in state.items]}
    )
    name = f"{plan.name} (copy)"[:80]
    return create_plan(
        db, plan.account_id, name, copy, is_primary=False, show_unpublished=show_unpublished
    )


def apply_to_plan(
    db: Session,
    plan: m.Plan,
    ops: list[ChangeOp],
    base_plan_hash: str,
    *,
    show_unpublished: bool,
) -> PlanState:
    """Apply `ops` if the plan still hashes to `base_plan_hash`; returns the new state."""
    state = read_state(db, plan)
    current = plan_hash(state)
    if current != base_plan_hash:
        raise StalePlanError(current)
    try:
        new = apply_ops(state, ops)
    except ChangeOpError as exc:
        raise InvalidPlanError(str(exc)) from exc
    write_state(db, plan, new, show_unpublished=show_unpublished)
    return new


# ------------------------------------------------------------------ change sets


def change_set_model(row: m.ChangeSet) -> ChangeSet:
    return ChangeSet(
        id=str(row.id),
        plan_id=str(row.plan_id),
        origin=row.origin,
        ops=_OPS.validate_python(row.ops),
        base_plan_hash=row.base_plan_hash,
        preview_report=Report.model_validate(row.preview_report) if row.preview_report else None,
        status=row.status,
    )


def store_change_set(
    db: Session,
    plan: m.Plan,
    *,
    origin: str,
    ops: list[ChangeOp],
    base_plan_hash: str,
    preview: Report | None,
) -> m.ChangeSet:
    row = m.ChangeSet(
        plan_id=plan.id,
        origin=origin,
        ops=_OPS.dump_python(ops, mode="json", by_alias=True),
        base_plan_hash=base_plan_hash,
        preview_report=preview.model_dump(mode="json", by_alias=True) if preview else None,
        status="proposed",
        created_day=dt.date.today(),
    )
    db.add(row)
    db.flush()
    return row


def owned_change_set(db: Session, plan: m.Plan, changeset_id: uuid.UUID) -> m.ChangeSet:
    row = db.get(m.ChangeSet, changeset_id)
    if row is None or row.plan_id != plan.id:
        raise PlanNotFoundError(str(changeset_id))
    return row


def list_change_sets(db: Session, plan: m.Plan) -> list[ChangeSet]:
    rows = db.scalars(
        sa.select(m.ChangeSet)
        .where(m.ChangeSet.plan_id == plan.id)
        .order_by(m.ChangeSet.created_day.desc(), m.ChangeSet.id)
    )
    return [change_set_model(r) for r in rows]


def selected_ops(ops: list[ChangeOp], terms: list[str] | None, state: PlanState) -> list[ChangeOp]:
    """'Apply selected quarters': keep the ops that touch a selected quarter (the item's
    current quarter, or where it is added or moved to)."""
    if terms is None:
        return ops
    chosen = set(terms)
    where = {i.id: i.term for i in state.items if i.id is not None}
    kept = []
    for op in ops:
        touched: set[Any] = {
            getattr(op, name, None) for name in ("term", "from_term", "to_term")
        } - {None}
        item_id = getattr(op, "item_id", None)
        if item_id is not None and item_id in where:
            touched.add(where[item_id])
        if touched & chosen:
            kept.append(op)
    return kept
