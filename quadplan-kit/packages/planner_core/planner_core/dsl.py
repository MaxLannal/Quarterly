"""Small pure helpers over the DSL: node paths and the human form of expressions."""

from __future__ import annotations

from collections.abc import Iterator
from fnmatch import fnmatchcase

from planner_core.models import (
    Atom,
    BoundedPartsNode,
    CollegePolicy,
    Expr,
    GroupNode,
    Part,
    ProgramRules,
    SelectNode,
    SlotNode,
)

AnyNode = GroupNode | SlotNode | SelectNode | BoundedPartsNode


def iter_nodes(program: ProgramRules) -> Iterator[tuple[str, AnyNode]]:
    """Yield `(path, node)` depth-first. The root's path is the program id; a child's path is
    its parent's path plus `/<child id>` (e.g. `cmsc-bs/intro/1`)."""

    def walk(path: str, node: AnyNode) -> Iterator[tuple[str, AnyNode]]:
        yield path, node
        if isinstance(node, GroupNode):
            for child in node.children:
                yield from walk(f"{path}/{child.id}", child)

    yield from walk(program.id, program.rules)


def iter_parts(program: ProgramRules) -> Iterator[tuple[str, Part]]:
    """Yield `(path, part)` for every part of every bounded_parts node."""
    for path, node in iter_nodes(program):
        if isinstance(node, BoundedPartsNode):
            for part in node.parts:
                yield f"{path}/{part.id}", part


def node_paths(program: ProgramRules) -> list[str]:
    """Every addressable path: nodes and bounded_parts parts."""
    return [p for p, _ in iter_nodes(program)] + [p for p, _ in iter_parts(program)]


def share_applies(with_: str, other: ProgramRules, college: CollegePolicy | None) -> bool:
    """Does a share limit's `with` name the program `other`? Forms: `type:<program type>`,
    `core` (the College's core program, or any program of type core), `program:<id glob>`,
    or a bare program id glob."""
    if with_.startswith("type:"):
        return other.type == with_[5:]
    if with_ == "core":
        return other.type == "core" or (college is not None and other.id == college.core_program_id)
    return fnmatchcase(other.id, with_.removeprefix("program:"))


def excepted(path: str, names: list[str]) -> bool:
    """Is the unit at `path` left out of a share limit? True when the path, or any node id
    on it below the program id, is listed in the limit's `except`."""
    return path in names or any(part in names for part in path.split("/")[1:])


def residency_fraction(program: ProgramRules, college: CollegePolicy | None) -> float | None:
    """Share of a program's courses that must be taken in residence: the program's own
    `policy.residency`, else the College value for programs other than the Core and
    study-abroad blocks."""
    if program.policy.residency is not None:
        return program.policy.residency.min_fraction
    if college is None or program.type in ("core", "study_abroad_block"):
        return None
    if program.id == college.core_program_id:
        return None
    return college.residency_min_fraction


def expr_courses(expr: Expr) -> set[str]:
    """Course codes named by `course` and `concurrent` atoms."""
    if expr.atom is not None:
        return {expr.atom.value} if expr.atom.kind in ("course", "concurrent") else set()
    found: set[str] = set()
    for child in expr.children:
        found |= expr_courses(child)
    return found


def _atom_text(atom: Atom) -> str:
    match atom.kind:
        case "course":
            grade = f" (grade {atom.min_grade} or higher)" if atom.min_grade else ""
            return f"{atom.value}{grade}"
        case "concurrent":
            return f"{atom.value} (may be taken concurrently)"
        case "placement":
            return f"placement into {atom.value}"
        case "standing":
            return f"{atom.value} standing"
        case "program":
            return f"enrolled in {atom.value}"
        case "consent":
            return f"consent of {atom.value}"


def expr_to_text(expr: Expr) -> str:
    """Human form for display, e.g. "CMSC 14200 and (MATH 15900 or MATH 16300)"."""
    if expr.atom is not None:
        return _atom_text(expr.atom)
    if expr.op == "n_of":
        return f"{expr.n} of ({', '.join(expr_to_text(c) for c in expr.children)})"
    joiner = " and " if expr.op == "all" else " or "
    return joiner.join(_wrapped(c) for c in expr.children)


def _wrapped(expr: Expr) -> str:
    text = expr_to_text(expr)
    return text if expr.op in ("atom", "n_of") else f"({text})"
