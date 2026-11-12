"""Compiles a program's rule tree into the pieces the solver model works on.

A *unit* is a place a course can be assigned to: a `slot`, a `select`, or one part of a
`bounded_parts` node. A *scope* is a node (or part) that carries set constraints
(`same_sequence`, `in_order`, `max_from`, `distinct_subjects`); they apply to every course
used anywhere below that node.

Inheritance: `no_pass_fail`, `min_grade` (the strictest wins) and `allow_double_count` set on
a group or a bounded_parts node apply to every unit below it.

Eligibility: a plan course is eligible for a unit when it matches the unit's selector, is not
taken Pass/Fail where that is forbidden, and has no recorded grade below the minimum.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planner_core.dsl import AnyNode
from planner_core.index import Index, PlanFacts, Taken, grade_ok
from planner_core.models import (
    Constraints,
    GroupNode,
    Part,
    ProgramRules,
    SelectNode,
    Selector,
    SlotNode,
)


@dataclass
class Unit:
    path: str
    kind: str  # "slot" | "select" | "part"
    label: str | None
    selector: Selector
    #: Courses needed (slot 1, select count, part minimum); 0 for a select by units.
    need: int
    #: Most courses the unit takes (slot 1, select count, part maximum); None = no cap.
    cap: int | None
    need_units: int | None
    no_pass_fail: bool
    min_grade: str | None
    double_count: bool
    eligible: list[Taken] = field(default_factory=list)
    #: Courses that match the selector but are taken Pass/Fail where that is forbidden (V12).
    blocked_pass_fail: list[Taken] = field(default_factory=list)
    #: Courses that match the selector but have a recorded grade below the minimum.
    blocked_grade: list[Taken] = field(default_factory=list)


@dataclass
class Scope:
    path: str
    constraints: Constraints
    #: Paths of the units below this node (the node itself when it is a unit).
    units: list[str]
    #: Path of the node whose satisfaction the constraints gate (a part's bounded_parts node).
    owner: str


@dataclass
class Compiled:
    program: ProgramRules
    units: dict[str, Unit] = field(default_factory=dict)  # in tree order
    scopes: list[Scope] = field(default_factory=list)
    #: Node path -> paths of the units below it.
    below: dict[str, list[str]] = field(default_factory=dict)


def stricter(a: str | None, b: str | None) -> str | None:
    """The higher of two grade minimums."""
    if a is None or b is None:
        return a or b
    return a if grade_ok(a, b) else b


def has_set_constraints(c: Constraints) -> bool:
    return bool(c.same_sequence or c.in_order or c.max_from or c.distinct_subjects)


def compile_program(program: ProgramRules, facts: PlanFacts, idx: Index) -> Compiled:
    out = Compiled(program=program)

    def unit(path: str, node: SlotNode | SelectNode | Part, inherited: Constraints) -> None:
        own = node.constraints
        need_units: int | None = None
        cap: int | None
        if isinstance(node, SlotNode):
            selector, need, cap = Selector(codes=node.any_of), 1, 1
        elif isinstance(node, SelectNode):
            selector, need_units = node.from_, node.units
            need, cap = (node.count, node.count) if node.count is not None else (0, None)
        else:
            selector, need, cap = node.from_, node.count[0], node.count[1]
        made = Unit(
            path=path,
            kind="part" if isinstance(node, Part) else node.kind,
            label=node.label,
            selector=selector,
            need=need,
            cap=cap,
            need_units=need_units,
            no_pass_fail=inherited.no_pass_fail or own.no_pass_fail,
            min_grade=stricter(inherited.min_grade, own.min_grade),
            double_count=inherited.allow_double_count or own.allow_double_count,
        )
        for taken in _candidates(selector, facts, idx):
            if not idx.matches(selector, taken.code):
                continue
            if made.no_pass_fail and taken.grading == "pass_fail":
                made.blocked_pass_fail.append(taken)
            elif not grade_ok(taken.grade, made.min_grade):
                made.blocked_grade.append(taken)
            else:
                made.eligible.append(taken)
        out.units[path] = made
        out.below[path] = [path]
        if has_set_constraints(own):
            owner = path.rsplit("/", 1)[0] if isinstance(node, Part) else path
            out.scopes.append(Scope(path=path, constraints=own, units=[path], owner=owner))

    def walk(path: str, node: AnyNode, inherited: Constraints) -> list[str]:
        if isinstance(node, SlotNode | SelectNode):
            unit(path, node, inherited)
            return [path]
        own = node.constraints
        passed = Constraints(
            no_pass_fail=inherited.no_pass_fail or own.no_pass_fail,
            min_grade=stricter(inherited.min_grade, own.min_grade),
            allow_double_count=inherited.allow_double_count or own.allow_double_count,
        )
        below: list[str] = []
        if isinstance(node, GroupNode):
            for child in node.children:
                below += walk(f"{path}/{child.id}", child, passed)
        else:
            for part in node.parts:
                unit(f"{path}/{part.id}", part, passed)
                below.append(f"{path}/{part.id}")
        out.below[path] = below
        if has_set_constraints(own):
            out.scopes.append(Scope(path=path, constraints=own, units=below, owner=path))
        return below

    walk(program.id, program.rules, Constraints())
    return out


def _candidates(selector: Selector, facts: PlanFacts, idx: Index) -> list[Taken]:
    """Plan courses that could match, narrowed cheaply when the selector names codes or a list."""
    keys: set[str] | frozenset[str] | None = None
    if selector.codes:
        keys = {idx.canon(code) for code in selector.codes}
    elif selector.list_ is not None:
        keys = idx.list_members(selector.list_)
    if keys is None:
        return list(facts.taken.values())
    return [facts.taken[k] for k in sorted(keys) if k in facts.taken]


def selectors_below(compiled: Compiled, scope: Scope) -> list[Selector]:
    return [compiled.units[path].selector for path in scope.units]


def out_of_order(a: Taken, b: Taken) -> bool:
    """`in_order`: two courses of one subject must be taken in ascending course-number order,
    in strictly increasing terms (a credit comes before every term)."""
    if a.code.split(" ")[0] != b.code.split(" ")[0] or a.code == b.code:
        return False
    first, second = (a, b) if a.code < b.code else (b, a)
    return second.term is not None and first.order >= second.order
