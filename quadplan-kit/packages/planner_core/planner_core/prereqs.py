"""Expression evaluation for prerequisites, co-requisites and restrictions (V03).

Semantics (SPEC "Prerequisite expressions"):
- `course`: met by a course completed, credited or planned in a strictly earlier term, or in
  the same term when that term is a Summer quarter (summer sessions run in sequence). A
  cross-listed, `equivalent` or `replaces` partner counts as the course. With `min_grade`, a
  completed course whose recorded grade is lower does not count; a course without a grade yet
  is assumed to meet it.
- `concurrent`: the same or an earlier term. Every `course` atom inside a `coreq` expression
  is read this way.
- `placement`: the value is in `plan.placements`, or a placement credit names it.
- `standing`: the student's class year in that term is at least the named standing.
- `program`: a glob matched against the plan's program ids.
- `consent`: never blocks; the evaluation reports it so the check can warn.

When several branches of `any` / `n_of` hold, the ones needing the fewest consents win, so a
student who has the course is not told to ask for consent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from planner_core.index import PlanFacts, Taken, grade_ok
from planner_core.models import STANDINGS, Atom, Expr
from planner_core.terms import is_summer


@dataclass
class Evaluation:
    ok: bool
    #: Witness tokens (see `PrereqWitness`) for the atoms that made the expression true.
    by: list[str] = field(default_factory=list)
    consents: list[str] = field(default_factory=list)
    #: Atoms that are not met, for messages and fix hints.
    missing: list[Atom] = field(default_factory=list)
    #: True when a course without a grade was assumed to meet a `min_grade`.
    assumed_grade: bool = False


def placement_values(facts: PlanFacts) -> set[str]:
    values = set(facts.plan.placements)
    for credit in facts.plan.credits:
        if credit.kind == "placement":
            values.add(credit.label)
            if credit.maps_to is not None:
                values.add(credit.maps_to)
    return values


def evaluate(expr: Expr, item: Taken, facts: PlanFacts, *, coreq: bool = False) -> Evaluation:
    """Evaluate `expr` for the plan item `item` (a course in a term)."""
    if expr.atom is not None:
        return _atom(expr.atom, item, facts, coreq)
    children = [evaluate(child, item, facts, coreq=coreq) for child in expr.children]
    passed = sorted((c for c in children if c.ok), key=lambda c: len(c.consents))
    need = {"all": len(children), "any": 1, "n_of": expr.n or 0}[expr.op]
    if len(passed) < need:
        return Evaluation(ok=False, missing=[a for c in children if not c.ok for a in c.missing])
    used = passed[:need]
    return Evaluation(
        ok=True,
        by=[token for c in used for token in c.by],
        consents=[value for c in used for value in c.consents],
        assumed_grade=any(c.assumed_grade for c in used),
    )


def _atom(atom: Atom, item: Taken, facts: PlanFacts, coreq: bool) -> Evaluation:
    assert item.term is not None
    if atom.kind in ("course", "concurrent"):
        # In a Summer quarter a prerequisite may sit in the same quarter (its sessions run in
        # sequence): `terms.is_summer`.
        strict = atom.kind == "course" and not coreq and not is_summer(item.term)
        hit = prior(atom.value, item, facts, strict=strict)
        if hit is None or not grade_ok(hit.grade, atom.min_grade):
            return Evaluation(ok=False, missing=[atom])
        assumed = atom.min_grade is not None and hit.grade is None
        return Evaluation(ok=True, by=[hit.ref], assumed_grade=assumed)
    if atom.kind == "placement":
        ok = atom.value in placement_values(facts)
    elif atom.kind == "standing":
        ok = facts.class_year(item.term) >= STANDINGS.index(atom.value) + 1
    elif atom.kind == "program":
        ok = any(fnmatchcase(p.program_id, atom.value) for p in facts.plan.programs)
    else:  # consent never blocks
        return Evaluation(ok=True, by=[f"consent:{atom.value}"], consents=[atom.value])
    if not ok:
        return Evaluation(ok=False, missing=[atom])
    return Evaluation(ok=True, by=[f"{atom.kind}:{atom.value}"])


def prior(code: str, item: Taken, facts: PlanFacts, *, strict: bool) -> Taken | None:
    """The earliest record of `code` (or an alternative) before `item`'s term, or in it when
    not `strict`. A course is never its own prerequisite."""
    hits = [
        facts.taken[key]
        for key in sorted(facts.idx.alts(code))
        if key in facts.taken and key != item.key
    ]
    hits = [t for t in hits if t.order < item.order or (not strict and t.order == item.order)]
    return min(hits, key=lambda t: (t.order, t.code), default=None)
