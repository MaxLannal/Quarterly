"""Node-level agreement between two rule trees (validator (d), the diff against last year,
and the pilot's comparison with the hand seed).

A node *agrees* when its meaning is the same: kind, counts, courses, selectors and
constraints. Labels, ids, source quotes, `needs_review` and weights are not compared, and
the order of course codes inside a list does not matter. The program-level policy is compared
as one extra node, `<program>/policy`.

Children are paired by id first, then by identical content, then by position, so two trees
that name their nodes differently still line up. A node only one tree has is a disagreement.
Agreement = agreed nodes / all nodes (the reference's nodes plus the candidate's extras).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from planner_core.hashing import canonical_json
from planner_core.models import BoundedPartsNode, GroupNode, Policy, ProgramRules

Unit = Any  # a node or a bounded_parts part

IGNORED = {"id", "label", "source", "needs_review", "weight", "children", "parts"}


def _sorted_codes(data: Any) -> Any:
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            value = _sorted_codes(value)
            if key in ("any_of", "codes", "exclude", "tags") and isinstance(value, list):
                value = sorted(value)
            out[key] = value
        return out
    if isinstance(data, list):
        return [_sorted_codes(v) for v in data]
    return data


def _strip_sources(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _strip_sources(v) for k, v in data.items() if not k.endswith("source")}
    if isinstance(data, list):
        return [_strip_sources(v) for v in data]
    return data


def content(unit: Unit) -> dict[str, Any]:
    """What a node means, without its children."""
    data = unit.model_dump(mode="json", by_alias=True, exclude=IGNORED)
    return _sorted_codes(_strip_sources(data))


def subtree(unit: Unit) -> str:
    """Content of a node and everything below it (for pairing renamed children)."""
    return canonical_json([content(unit), [subtree(c) for c in _children(unit)]])


def _children(unit: Unit) -> list[Unit]:
    if isinstance(unit, GroupNode):
        return list(unit.children)
    if isinstance(unit, BoundedPartsNode):
        return list(unit.parts)
    return []


def _key(unit: Unit) -> str:
    return unit.id or ""


@dataclass
class Disagreement:
    path: str
    reference: dict[str, Any] | None
    candidate: dict[str, Any] | None

    @property
    def kind(self) -> str:
        if self.reference is None:
            return "extra"
        if self.candidate is None:
            return "missing"
        return "different"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "reference": self.reference,
            "candidate": self.candidate,
        }


@dataclass
class Agreement:
    total: int = 0
    agreed: int = 0
    disagreements: list[Disagreement] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.agreed / self.total if self.total else 1.0

    @property
    def identical(self) -> bool:
        return not self.disagreements

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "agreed": self.agreed,
            "rate": round(self.rate, 4),
            "disagreements": [d.as_dict() for d in self.disagreements],
        }


def _count(unit: Unit) -> int:
    return 1 + sum(_count(c) for c in _children(unit))


def _only_one(out: Agreement, path: str, unit: Unit, side: str) -> None:
    def walk(p: str, u: Unit) -> None:
        out.total += 1
        data = content(u)
        out.disagreements.append(
            Disagreement(
                p, data if side == "reference" else None, data if side == "candidate" else None
            )
        )
        for c in _children(u):
            walk(f"{p}/{_key(c)}", c)

    walk(path, unit)


def _pair(
    ref: list[Unit], cand: list[Unit]
) -> tuple[list[tuple[Unit, Unit]], list[Unit], list[Unit]]:
    pairs: list[tuple[Unit, Unit]] = []
    left = list(ref)
    right = list(cand)
    for step in ("id", "subtree", "position"):
        for r in list(left):
            match = None
            for c in right:
                if (
                    (step == "id" and r.id and c.id == r.id)
                    or (step == "subtree" and subtree(c) == subtree(r))
                    or (step == "position" and type(c) is type(r))
                ):
                    match = c
                if match is not None:
                    break
            if match is not None:
                pairs.append((r, match))
                left.remove(r)
                right.remove(match)
    return pairs, left, right


def _walk(out: Agreement, path: str, ref: Unit, cand: Unit) -> None:
    out.total += 1
    a, b = content(ref), content(cand)
    if a == b:
        out.agreed += 1
    else:
        out.disagreements.append(Disagreement(path, a, b))
    pairs, missing, extra = _pair(_children(ref), _children(cand))
    for r, c in pairs:
        _walk(out, f"{path}/{_key(r)}", r, c)
    for r in missing:
        _only_one(out, f"{path}/{_key(r)}", r, "reference")
    for c in extra:
        _only_one(out, f"{path}/{_key(c)}", c, "candidate")


def _policy_data(policy: Policy) -> dict[str, Any]:
    return _sorted_codes(_strip_sources(policy.model_dump(mode="json", by_alias=True)))


def node_agreement(reference: ProgramRules, candidate: ProgramRules) -> Agreement:
    out = Agreement()
    _walk(out, reference.id, reference.rules, candidate.rules)
    ref_policy, cand_policy = _policy_data(reference.policy), _policy_data(candidate.policy)
    empty = _policy_data(Policy())
    if ref_policy != empty or cand_policy != empty:
        out.total += 1
        if ref_policy == cand_policy:
            out.agreed += 1
        else:
            out.disagreements.append(
                Disagreement(f"{reference.id}/policy", ref_policy, cand_policy)
            )
    return out


def count_nodes(rules: ProgramRules) -> int:
    return _count(rules.rules)


__all__ = ["Agreement", "Disagreement", "content", "count_nodes", "node_agreement"]
