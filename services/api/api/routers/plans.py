"""Saved plans, item edits, change sets and the deterministic plan generator (prompt 06).

Every endpoint except `POST /plans/generate` needs a logged-in account and only sees that
account's plans (another account's plan is a 404). State-changing requests carry the CSRF
token (app-wide guard). A change set is applied only while the plan still hashes to the
change set's `base_plan_hash`; otherwise it is marked `stale`, re-previewed against the
current plan, and the request is refused with 409.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from planner_core import verify_checked
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.generator import generate, horizon
from planner_core.hashing import plan_hash
from planner_core.models import (
    AddOp,
    Catalog,
    ChangeOp,
    ChangeSet,
    GenerateOptions,
    Infeasibility,
    LockOp,
    MoveOp,
    PlanState,
    RuleSet,
    Variant,
)
from sqlalchemy.orm import Session

from api.agents.planner.chat import confirmation_problem
from api.auth.ratelimit import DAY, Limit, account_subject, ip_limit
from api.auth.sessions import current_account
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.repo import plans as repo
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.schemas.plans import (
    ChangeSetApply,
    GeneratedVariant,
    GenerateLocal,
    GenerateOut,
    ItemsPatch,
    PlanComparison,
    PlanCreate,
    PlanImport,
    PlanOut,
    PlanSummary,
    PlanUpdate,
)

router = APIRouter(prefix="/plans", tags=["plans"])
logger = logging.getLogger("api.plans")

Db = Annotated[Session, Depends(get_session)]
Me = Annotated[m.Account, Depends(current_account)]


def _unpublished() -> bool:
    return get_settings().show_unpublished_programs


def _plan(db: Session, me: m.Account, plan_id: uuid.UUID) -> m.Plan:
    try:
        return repo.owned_plan(db, me.id, plan_id)
    except repo.PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Plan not found.") from exc


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _stale(current: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"message": "The plan changed since you last loaded it.", "plan_hash": current},
    )


@router.get("", response_model=list[PlanSummary])
def list_plans(db: Db, me: Me) -> list[PlanSummary]:
    return repo.list_plans(db, me.id)


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(body: PlanCreate, db: Db, me: Me) -> PlanOut:
    try:
        plan = repo.create_plan(
            db,
            me.id,
            body.name,
            body.state,
            is_primary=body.is_primary,
            show_unpublished=_unpublished(),
        )
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    db.commit()
    return repo.plan_out(db, plan)


@router.post("/import", response_model=list[PlanSummary])
def import_plans(body: PlanImport, db: Db, me: Me) -> list[PlanSummary]:
    """Logged-out plans from the browser, saved at login. All or nothing."""
    try:
        made = [
            repo.create_plan(
                db,
                me.id,
                p.name,
                p.state,
                is_primary=p.is_primary,
                show_unpublished=_unpublished(),
            )
            for p in body.plans
        ]
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    db.commit()
    return [repo.summary(p) for p in made]


def _load(db: Session, state: PlanState, *, whole: bool = False) -> tuple[RuleSet, Catalog]:
    try:
        return load_verify_inputs(
            db,
            state,
            show_unpublished=_unpublished(),
            whole_catalog=whole,
            section_terms=horizon(state) if whole else None,
        )
    except UnknownProgramsError as exc:
        raise HTTPException(
            status_code=422, detail=f"Unknown program(s): {', '.join(exc.program_ids)}"
        ) from exc


#: Most solver time one request may ask for (the client sends `time_limit_s`).
MAX_GENERATE_SECONDS = 5.0
#: Generations per account per day (on top of the per-IP limit on the routes).
GENERATE_PER_ACCOUNT = Limit("generate:account", 100, DAY)


def _generate(
    db: Session, state: PlanState, options: GenerateOptions
) -> tuple[list[Variant], Infeasibility | None]:
    options = options.model_copy(
        update={"time_limit_s": min(options.time_limit_s, MAX_GENERATE_SECONDS)}
    )
    rules, catalog = _load(db, state, whole=True)
    result = generate(state, rules, catalog, options)
    for alert in result.alerts:
        logger.error("%s", alert)  # a verified-plan bug; no user data in the message
    return result.variants, result.infeasible


@router.post(
    "/generate",
    response_model=GenerateOut,
    dependencies=[Depends(ip_limit("generate", 200))],
)
def generate_local(
    body: GenerateLocal, db: Db, mode: Literal["deterministic"] = "deterministic"
) -> GenerateOut:
    """Generate for a plan that lives in the browser. Nothing is saved: the change sets come
    back without ids, and the browser applies the chosen one itself."""
    variants, infeasible = _generate(db, body.plan, body.options)
    base = plan_hash(body.plan)
    return GenerateOut(
        variants=[
            GeneratedVariant(
                label=v.label,
                change_set=ChangeSet(
                    origin="generate", ops=v.ops, base_plan_hash=base, preview_report=v.report
                ),
                plan=v.plan,
                report=v.report,
                metrics=v.metrics,
                rationale=v.rationale,
            )
            for v in variants
        ],
        infeasible=infeasible,
    )


def _diff(a: PlanState, b: PlanState) -> list[ChangeOp]:
    """Operations that turn plan a's courses into plan b's (by course and quarter)."""
    from planner_core.models import AddOp, RemoveOp

    left = [(i.course or i.slot_ref or "", i.term) for i in a.items]
    right = [(i.course or i.slot_ref or "", i.term) for i in b.items]
    ops: list[ChangeOp] = []
    unmatched_right = list(right)
    only_left = []
    for entry in left:
        if entry in unmatched_right:
            unmatched_right.remove(entry)
        else:
            only_left.append(entry)
    for name, term in only_left:
        moved = next((r for r in unmatched_right if r[0] == name), None)
        field = "course" if " " in name else "slot_ref"
        if moved is not None:
            unmatched_right.remove(moved)
            ops.append(MoveOp(**{field: name}, from_term=term, to_term=moved[1]))
        else:
            ops.append(RemoveOp(**{field: name}, term=term))
    for name, term in unmatched_right:
        field = "course" if " " in name else "slot_ref"
        ops.append(AddOp(**{field: name}, term=term))
    return ops


def _metrics(state: PlanState) -> dict[str, float]:
    courses = [i for i in state.items if i.course]
    return {
        "courses": float(len(courses)),
        "quarters": float(len({i.term for i in courses})),
        "units": float(sum(i.units or 100 for i in courses)),
    }


@router.get("/compare", response_model=PlanComparison)
def compare_plans(a: uuid.UUID, b: uuid.UUID, db: Db, me: Me) -> PlanComparison:
    pa, pb = repo.plan_out(db, _plan(db, me, a)), repo.plan_out(db, _plan(db, me, b))
    return PlanComparison(
        a=pa,
        b=pb,
        ops_a_to_b=_diff(pa.state, pb.state),
        metrics={"a": _metrics(pa.state), "b": _metrics(pb.state)},
    )


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: uuid.UUID, db: Db, me: Me) -> PlanOut:
    return repo.plan_out(db, _plan(db, me, plan_id))


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(plan_id: uuid.UUID, body: PlanUpdate, db: Db, me: Me) -> PlanOut:
    plan = _plan(db, me, plan_id)
    try:
        repo.update_plan(
            db,
            plan,
            name=body.name,
            is_primary=body.is_primary,
            state=body.state,
            show_unpublished=_unpublished(),
        )
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    db.commit()
    return repo.plan_out(db, plan)


@router.delete("/{plan_id}", status_code=204, response_class=Response)
def delete_plan(plan_id: uuid.UUID, db: Db, me: Me) -> None:
    from api.agents.planner.chat import forget_chats

    plan = _plan(db, me, plan_id)
    forget_chats(db, [plan.id])
    db.delete(plan)
    db.commit()


@router.post("/{plan_id}/duplicate", response_model=PlanOut, status_code=201)
def duplicate_plan(plan_id: uuid.UUID, db: Db, me: Me) -> PlanOut:
    copy = repo.duplicate_plan(db, _plan(db, me, plan_id), show_unpublished=_unpublished())
    db.commit()
    return repo.plan_out(db, copy)


@router.patch("/{plan_id}/items", response_model=PlanOut)
def patch_items(plan_id: uuid.UUID, body: ItemsPatch, db: Db, me: Me) -> PlanOut:
    plan = _plan(db, me, plan_id)
    try:
        repo.apply_to_plan(
            db, plan, list(body.ops), body.base_plan_hash, show_unpublished=_unpublished()
        )
    except repo.StalePlanError as exc:
        db.rollback()
        raise _stale(exc.current_hash) from exc
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    db.commit()
    return repo.plan_out(db, plan)


@router.post(
    "/{plan_id}/generate",
    response_model=GenerateOut,
    dependencies=[Depends(ip_limit("generate", 200))],
)
def generate_saved(
    plan_id: uuid.UUID,
    options: GenerateOptions,
    db: Db,
    me: Me,
    store: Annotated[Store, Depends(get_store)],
    mode: Literal["deterministic"] = "deterministic",
) -> GenerateOut:
    """Generate up to 3 verified variants without an LLM (`mode=deterministic`; the agent
    mode arrives with prompt 07). Each variant is stored as a proposed change set."""
    plan = _plan(db, me, plan_id)
    GENERATE_PER_ACCOUNT.hit(store, account_subject(me.id))
    state = repo.read_state(db, plan)
    variants, infeasible = _generate(db, state, options)
    base = plan_hash(state)
    out = []
    for v in variants:
        row = repo.store_change_set(
            db, plan, origin="generate", ops=v.ops, base_plan_hash=base, preview=v.report
        )
        out.append(
            GeneratedVariant(
                label=v.label,
                change_set=repo.change_set_model(row),
                plan=v.plan,
                report=v.report,
                metrics=v.metrics,
                rationale=v.rationale,
            )
        )
    db.commit()
    return GenerateOut(variants=out, infeasible=infeasible)


@router.get("/{plan_id}/changesets", response_model=list[ChangeSet])
def list_change_sets(plan_id: uuid.UUID, db: Db, me: Me) -> list[ChangeSet]:
    return repo.list_change_sets(db, _plan(db, me, plan_id))


def _change_set(db: Session, plan: m.Plan, changeset_id: uuid.UUID) -> m.ChangeSet:
    try:
        return repo.owned_change_set(db, plan, changeset_id)
    except repo.PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Change set not found.") from exc


@router.post("/{plan_id}/changesets/{changeset_id}/apply", response_model=PlanOut)
def apply_change_set(
    plan_id: uuid.UUID, changeset_id: uuid.UUID, body: ChangeSetApply, db: Db, me: Me
) -> PlanOut:
    plan = _plan(db, me, plan_id)
    row = _change_set(db, plan, changeset_id)
    if body.confirmation_text is not None:
        # A typed confirmation from the advisor chat (prompt 07): parsed deterministically,
        # it must name this change set; the plan-hash check below still applies.
        problem = confirmation_problem(db, plan, row, body.confirmation_text, body.terms)
        if problem is not None:
            raise HTTPException(status_code=422, detail=problem)
    if row.status != "proposed":
        raise HTTPException(status_code=409, detail=f"This change set is {row.status}.")
    state = repo.read_state(db, plan)
    current = plan_hash(state)
    if row.run_id is not None and body.confirmation_text is None:
        return _apply_planner_proposal(db, plan, row, state, current, body.terms)
    if body.base_plan_hash != current and row.base_plan_hash == current:
        raise _stale(current)  # only the client's copy is old; the change set still fits
    if current != row.base_plan_hash:
        # The plan moved on: mark the change set stale and re-preview it on the current plan.
        row.status = "stale"
        cs = repo.change_set_model(row)
        try:
            preview_plan = apply_ops(state, cs.ops)
            rules, catalog = _load(db, preview_plan)
            report, _ = verify_checked(preview_plan, rules, catalog)
            row.preview_report = report.model_dump(mode="json", by_alias=True)
        except (ChangeOpError, HTTPException):
            row.preview_report = None
        db.commit()
        raise _stale(current)
    cs = repo.change_set_model(row)
    ops = repo.selected_ops(cs.ops, body.terms, state)
    if not ops:
        raise HTTPException(status_code=422, detail="No changes in the selected quarters.")
    try:
        repo.apply_to_plan(db, plan, ops, current, show_unpublished=_unpublished())
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    row.status = "applied"
    db.commit()
    return repo.plan_out(db, plan)


NO_LONGER_FITS = "This proposal no longer fits your plan."


def _apply_planner_proposal(
    db: Session,
    plan: m.Plan,
    row: m.ChangeSet,
    state: PlanState,
    current: str,
    terms: list[str] | None,
) -> PlanOut:
    """A planner proposal (issue #17) re-bases onto later edits: the student accepts the
    proposals of one run one by one, and they stay while other edits happen (#18 D1). It applies
    while its ops still fit the current plan; otherwise it becomes stale. The courses it places
    are locked (#18 step 13)."""
    ops = repo.selected_ops(list(repo.change_set_model(row).ops), terms, state)
    if not ops:
        raise HTTPException(status_code=422, detail="No changes in the selected quarters.")
    locks: list[ChangeOp] = [
        LockOp(course=op.course, term=op.term if isinstance(op, AddOp) else op.to_term)
        for op in ops
        if isinstance(op, AddOp | MoveOp) and op.course
    ]
    try:
        apply_ops(state, [*ops, *locks])
    except ChangeOpError as exc:
        row.status = "stale"
        db.commit()
        raise HTTPException(status_code=409, detail=NO_LONGER_FITS) from exc
    try:
        repo.apply_to_plan(db, plan, [*ops, *locks], current, show_unpublished=_unpublished())
    except repo.InvalidPlanError as exc:
        db.rollback()
        raise _invalid(exc) from exc
    row.status = "applied"
    db.commit()
    return repo.plan_out(db, plan)


@router.post("/{plan_id}/changesets/{changeset_id}/discard", response_model=ChangeSet)
def discard_change_set(plan_id: uuid.UUID, changeset_id: uuid.UUID, db: Db, me: Me) -> ChangeSet:
    plan = _plan(db, me, plan_id)
    row = _change_set(db, plan, changeset_id)
    if row.status == "applied":
        raise HTTPException(status_code=409, detail="An applied change set cannot be discarded.")
    row.status = "discarded"
    db.commit()
    return repo.change_set_model(row)
