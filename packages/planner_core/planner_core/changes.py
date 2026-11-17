"""Applying change-set operations to a plan. Pure: returns a new PlanState."""

from __future__ import annotations

from collections.abc import Sequence

from planner_core.models import (
    AddOp,
    ChangeOp,
    ItemTarget,
    LockOp,
    MoveOp,
    PlanItem,
    PlanState,
    RemoveOp,
    UnlockOp,
)


class ChangeOpError(ValueError):
    """An operation does not fit the plan (unknown or ambiguous target, locked item)."""


def _find(items: list[PlanItem], target: ItemTarget, term: str | None) -> int:
    hits = [
        i
        for i, item in enumerate(items)
        if (target.item_id is None or item.id == target.item_id)
        and (target.course is None or item.course == target.course)
        and (target.slot_ref is None or item.slot_ref == target.slot_ref)
        and (term is None or item.term == term)
    ]
    label = target.item_id or target.course or target.slot_ref
    if not hits:
        raise ChangeOpError(f"no plan item matches {label}" + (f" in {term}" if term else ""))
    if len(hits) > 1:
        raise ChangeOpError(f"{label} matches {len(hits)} items; give the term")
    return hits[0]


def apply_ops(plan: PlanState, ops: Sequence[ChangeOp]) -> PlanState:
    """Apply `ops` in order. Locked items cannot be moved or removed (unlock first)."""
    items = [item.model_copy() for item in plan.items]
    for op in ops:
        if isinstance(op, AddOp):
            items.append(
                PlanItem(
                    course=op.course,
                    slot_ref=op.slot_ref,
                    term=op.term,
                    status=op.status,
                    units=op.units,
                    grading=op.grading,
                    locked=op.locked,
                )
            )
            continue
        term = op.from_term if isinstance(op, MoveOp) else op.term
        idx = _find(items, op, term)
        item = items[idx]
        if isinstance(op, LockOp | UnlockOp):
            items[idx] = item.model_copy(update={"locked": isinstance(op, LockOp)})
        elif item.locked:
            raise ChangeOpError(f"{item.course or item.slot_ref} in {item.term} is locked")
        elif isinstance(op, MoveOp):
            items[idx] = item.model_copy(update={"term": op.to_term})
        elif isinstance(op, RemoveOp):
            del items[idx]
    return plan.model_copy(update={"items": items})
