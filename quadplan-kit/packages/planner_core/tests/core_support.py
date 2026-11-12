"""Tiny builders for verifier tests (importable: pytest's `pythonpath` includes this folder).
Everything here is fake data; no real catalog facts."""

from __future__ import annotations

from typing import Any

from planner_core.models import (
    Catalog,
    CollegePolicy,
    Course,
    PlanState,
    ProgramRules,
    Report,
    Requisite,
    RuleSet,
)

YEAR = "2026-27"
ENTRY = "2026-AU"
#: Benchmark name -> milliseconds, filled by test_benchmark and printed by conftest.py.
BENCHMARK: dict[str, float] = {}
SRC = {"url": "https://example.invalid/fake", "quote": "FAKE"}
#: Plan years 1-4, quarters in order: T[0] = 2026-AU, T[1] = 2027-WI, T[2] = 2027-SP, ...
T = [f"{2026 + y + (q != 'AU')}-{q}" for y in range(4) for q in ("AU", "WI", "SP")]


def course(code: str, **fields: Any) -> Course:
    return Course(code=code, title=fields.pop("title", code), **fields)


def catalog(courses: list[str | Course], **fields: Any) -> Catalog:
    made = [c if isinstance(c, Course) else course(c) for c in courses]
    return Catalog.model_validate({"catalog_year": YEAR, "courses": made, **fields})


def program(pid: str, rules: dict[str, Any], **fields: Any) -> ProgramRules:
    fields.setdefault("type", "major")
    return ProgramRules.model_validate({"id": pid, "catalog_year": YEAR, "rules": rules, **fields})


def college(**fields: Any) -> CollegePolicy:
    """College policy with a fake source for every value given."""
    unsourced = ("overload_reasons", "core_program_id", "language_node", "needs_review")
    sources = {k: SRC for k in fields if k not in unsourced}
    return CollegePolicy.model_validate({"catalog_year": YEAR, "sources": sources, **fields})


def ruleset(
    *programs: ProgramRules,
    college: CollegePolicy | None = None,
    prereqs: dict[str, Any] | None = None,
    requisites: list[Requisite] | None = None,
) -> RuleSet:
    reqs = list(requisites or [])
    reqs += [
        Requisite.model_validate({"course": c, "prereq": e}) for c, e in (prereqs or {}).items()
    ]
    return RuleSet(catalog_year=YEAR, programs=list(programs), college=college, requisites=reqs)


def plan(
    items: dict[str, list[Any]] | None = None, programs: list[str] | None = None, **fields: Any
) -> PlanState:
    """`items` maps a term to courses: a code, or a dict of PlanItem fields."""
    rows: list[dict[str, Any]] = []
    for term, entries in (items or {}).items():
        for entry in entries:
            row = {"course": entry} if isinstance(entry, str) else dict(entry)
            rows.append({"term": term, **row})
    return PlanState.model_validate(
        {
            "catalog_year": YEAR,
            "entry_term": ENTRY,
            "items": rows,
            "programs": [{"program_id": p} for p in programs or []],
            **fields,
        }
    )


def found(report: Report, code: str, level: str | None = None) -> list[Any]:
    return [i for i in report.issues if i.code == code and (level is None or i.level == level)]


def error_codes(report: Report) -> set[str]:
    return {i.code for i in report.issues if i.level == "error"}


def warning_codes(report: Report) -> set[str]:
    return {i.code for i in report.issues if i.level == "warning"}
