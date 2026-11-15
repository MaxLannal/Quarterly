"""Validators (a)-(g) of SPEC "Annual catalog pipeline" step 6. All deterministic except (e),
whose judge is agent E4 (`worker.ingest.e4`); this module only scores its answer.

(a) schema: the tree parses as `planner_core.models.ProgramRules`, and every node, part,
    cap and policy entry carries a source.
(b) references: every course code and course list the tree names exists in the catalog.
(c) quotes: every quote appears verbatim (entities decoded, whitespace collapsed) in the
    snapshot it points at (by `snapshot_id`, else by `url`).
(d) agreement: the two independent E3 runs agree node by node.
(e) back-translation: E4 found no difference between its English rendering and the source.
(f) golden plans pass or fail as expected.
(g) size: a major needs between 9 and 19 courses (SPEC, Degree Requirements).
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from planner_core.dsl import iter_nodes, iter_parts
from planner_core.models import (
    BoundedPartsNode,
    GroupNode,
    ProgramRules,
    SelectNode,
    Selector,
    SlotNode,
    Source,
)
from pydantic import ValidationError

from worker.ingest.catalog import CatalogView
from worker.ingest.compare import Agreement
from worker.ingest.courseleaf import normalize
from worker.ingest.golden import GoldenOutcome

MAJOR_MIN_COURSES, MAJOR_MAX_COURSES = 9, 19

NAMES = {
    "a": "Schema",
    "b": "Courses and lists exist",
    "c": "Quotes are verbatim",
    "d": "Two runs agree",
    "e": "Back-translation matches the source",
    "f": "Golden plans",
    "g": "Size of a major",
}


@dataclass
class Check:
    id: str
    ok: bool
    problems: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def name(self) -> str:
        return NAMES[self.id]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ok": self.ok,
            "skipped": self.skipped,
            "problems": self.problems,
        }


def _check(id_: str, problems: list[str]) -> Check:
    return Check(id_, ok=not problems, problems=problems)


def skipped(id_: str, why: str) -> Check:
    return Check(id_, ok=True, problems=[why], skipped=True)


def sources_of(rules: ProgramRules) -> Iterator[tuple[str, Source | None]]:
    """(path, source) for every node, part, `max_from` cap and policy entry."""
    for path, unit in [*iter_nodes(rules), *iter_parts(rules)]:
        yield path, unit.source
        for i, cap in enumerate(unit.constraints.max_from):
            yield f"{path}/max_from[{i}]", cap.source
    policy = rules.policy
    for i, limit in enumerate(policy.share):
        yield f"{rules.id}/policy/share[{i}]", limit.source
    if policy.residency is not None:
        yield f"{rules.id}/policy/residency", policy.residency.source
    if policy.timing is not None:
        yield f"{rules.id}/policy/timing", policy.timing.source
    if policy.requires:
        yield f"{rules.id}/policy/requires", policy.requires_source
    if policy.excludes:
        yield f"{rules.id}/policy/excludes", policy.excludes_source


# ------------------------------------------------------------------------------- (a)


def check_schema(raw: Any) -> tuple[ProgramRules | None, Check]:
    try:
        rules = ProgramRules.model_validate(raw)
    except ValidationError as exc:
        problems = [
            f"{'.'.join(str(p) for p in e['loc']) or '(tree)'}: {e['msg']}"
            for e in exc.errors()[:20]
        ]
        return None, _check("a", problems)
    missing = [f"{path}: no source quote" for path, src in sources_of(rules) if src is None]
    return rules, _check("a", missing)


# ------------------------------------------------------------------------------- (b)


def _selector_refs(sel: Selector) -> tuple[set[str], set[str]]:
    codes = set(sel.codes) | set(sel.exclude)
    lists = {sel.list_} if sel.list_ else set()
    for sub in sel.union:
        c, lst = _selector_refs(sub)
        codes |= c
        lists |= lst
    return codes, lists


def references(rules: ProgramRules) -> tuple[set[str], set[str]]:
    """Every course code and course-list name the tree names."""
    codes: set[str] = set()
    lists: set[str] = set()
    for _, unit in [*iter_nodes(rules), *iter_parts(rules)]:
        if isinstance(unit, SlotNode):
            codes |= set(unit.any_of)
        sel = getattr(unit, "from_", None)
        if sel is not None:
            c, lst = _selector_refs(sel)
            codes |= c
            lists |= lst
        for cap in unit.constraints.max_from:
            c, lst = _selector_refs(cap.selector)
            codes |= c
            lists |= lst
    if rules.policy.timing is not None:
        codes |= set(rules.policy.timing.apply_requires)
    return codes, lists


def check_references(rules: ProgramRules, catalog: CatalogView) -> Check:
    codes, lists = references(rules)
    problems = [f"unknown course {c}" for c in sorted(codes) if not catalog.has_course(c)]
    problems += [f"unknown course list {n}" for n in sorted(lists) if not catalog.has_list(n)]
    return _check("b", problems)


# ------------------------------------------------------------------------------- (c)


def quote_found(quote: str, page: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in page


def check_quotes(
    rules: ProgramRules, texts_by_id: Mapping[str, str], ids_by_url: Mapping[str, str]
) -> Check:
    """`texts_by_id`: normalized page text per snapshot id; `ids_by_url`: snapshot id per URL."""
    problems = []
    for path, src in sources_of(rules):
        if src is None:
            continue
        sid = src.snapshot_id or ids_by_url.get(src.url or "")
        if sid is None or sid not in texts_by_id:
            problems.append(
                f"{path}: the quote points at a page that was not fetched "
                f"({src.url or src.snapshot_id})"
            )
        elif not quote_found(src.quote, texts_by_id[sid]):
            problems.append(f"{path}: quote not found verbatim: {src.quote[:120]!r}")
    return _check("c", problems)


# --------------------------------------------------------------------------- (d)-(f)


def check_agreement(agreement: Agreement | None) -> Check:
    if agreement is None:
        return skipped("d", "the second run did not produce a tree")
    problems = [f"{d.path}: {d.kind}" for d in agreement.disagreements]
    return _check("d", problems)


def check_backtranslation(differences: list[dict[str, str]] | None) -> Check:
    if differences is None:
        return skipped("e", "the back-translation judge did not answer")
    return _check(
        "e", [f"{d.get('path') or '(program)'}: {d.get('problem', '')}" for d in differences]
    )


def check_golden(outcome: GoldenOutcome | None) -> Check:
    if outcome is None or outcome.skipped:
        return skipped("f", "no golden plans for this program")
    return _check("f", list(outcome.failures))


# ------------------------------------------------------------------------------- (g)


def min_courses(unit: Any) -> int:
    """Fewest courses that satisfy a node (units count as 100 per course)."""
    if isinstance(unit, SlotNode):
        return 1
    if isinstance(unit, SelectNode):
        return unit.count if unit.count is not None else math.ceil((unit.units or 0) / 100)
    if isinstance(unit, BoundedPartsNode):
        if unit.total.courses is not None:
            return unit.total.courses
        return math.ceil((unit.total.units or 0) / 100)
    if isinstance(unit, GroupNode):
        needs = sorted(min_courses(c) for c in unit.children)
        return sum(needs) if unit.all else sum(needs[: unit.n_of or 0])
    return 0


def check_size(rules: ProgramRules, program_type: str | None) -> Check:
    if (program_type or rules.type) != "major":
        return skipped("g", "only majors have a size range")
    n = min_courses(rules.rules)
    if MAJOR_MIN_COURSES <= n <= MAJOR_MAX_COURSES:
        return _check("g", [])
    return _check(
        "g",
        [
            f"the major needs at least {n} courses; majors fall within "
            f"{MAJOR_MIN_COURSES}-{MAJOR_MAX_COURSES}"
        ],
    )


def deterministic_problems(
    raw: Any,
    catalog: CatalogView,
    texts_by_id: Mapping[str, str],
    ids_by_url: Mapping[str, str],
    program_type: str | None,
) -> tuple[ProgramRules | None, list[Check]]:
    """(a), (b), (c) and (g): what E3's `validate_rules` tool reports back."""
    rules, schema = check_schema(raw)
    if rules is None:
        return None, [schema]
    return rules, [
        schema,
        check_references(rules, catalog),
        check_quotes(rules, texts_by_id, ids_by_url),
        check_size(rules, program_type),
    ]
