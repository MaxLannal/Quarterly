"""Prompt 06: 20 synthetic student profiles on the real 2026-27 seed. Every result is a verified
plan (re-checked here independently) or a correct infeasibility explanation, in under 5 s."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from api.seed.bundle import SeedBundle, build_catalog, build_rules, load_bundle
from planner_core import check_certificate, verify
from planner_core.changes import apply_ops
from planner_core.generator import generate
from planner_core.models import Catalog, GenerateOptions, PlanState

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"
LIMIT_S = 5.0
CALC = ["MATH 15100"]
#: Profiles with no plan, and the exact set of limits the explanation must name.
CONFLICTS = {
    "first-year, no placement yet": {"program:cmsc-bs"},
    "transfer, CS BA": {"graduation", "load"},
    "transfer, Economics": {"graduation", "load"},
    "graduate early: impossible": {"graduation", "load", "goal:g"},
    "three courses a quarter": {"graduation", "goal:l"},
}


@pytest.fixture(scope="module")
def world() -> tuple[SeedBundle, Catalog]:
    bundle = load_bundle(SEED)
    return bundle, build_catalog(bundle)


def plan(programs: list[str], **extra: Any) -> PlanState:
    data: dict[str, Any] = {
        "catalog_year": "2026-27",
        "entry_term": "2026-AU",
        "programs": [{"program_id": p} for p in programs],
        "placements": CALC,
    }
    data.update(extra)
    return PlanState.model_validate(data)


def done(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"course": c, "term": t, "status": "completed", "grade": "A"} for c, t in pairs]


Y1 = [
    ("MATH 15100", "2026-AU"),
    ("CMSC 14100", "2026-AU"),
    ("HUMA 11000", "2026-AU"),
    ("MATH 15200", "2027-WI"),
    ("CMSC 14200", "2027-WI"),
    ("HUMA 11100", "2027-WI"),
    ("MATH 15300", "2027-SP"),
    ("CMSC 14300", "2027-SP"),
    ("HUMA 11200", "2027-SP"),
]

# (id, plan, options, expectation, message fragment)
PROFILES: list[tuple[str, PlanState, dict[str, Any], str, str]] = [
    ("first-year undecided", plan(["core"]), {}, "plan", ""),
    (
        "first-year undecided, interests",
        plan(["core"]),
        {"interests": ["philosophy", "music"]},
        "plan",
        "",
    ),
    (
        "first-year, no placement yet",
        plan(["core", "cmsc-bs"], placements=[]),
        {},
        "infeasible",
        "placement result",
    ),
    ("CS BA", plan(["core", "cmsc-ba"]), {"variants": 2}, "plan", ""),
    ("CS BS", plan(["core", "cmsc-bs"]), {"variants": 3}, "plan", ""),
    ("Math BS", plan(["core", "math-bs"]), {}, "plan", ""),
    ("Economics", plan(["core", "econ-ba"]), {}, "plan", ""),
    ("CS BS + Math BS", plan(["core", "cmsc-bs", "math-bs"]), {}, "plan", ""),
    (
        "CS + Math + Bx/MS",
        plan(
            ["core", "cmsc-bs", "math-bs", "cmsc-bxms-1"],
            goals=[{"id": "bx", "type": "bxms", "program_id": "cmsc-bxms-1", "apply_by": "Y3-WI"}],
        ),
        {},
        "plan",
        "",
    ),
    (
        "transfer, CS BA",
        plan(
            ["core", "cmsc-ba"],
            entry_term="2027-AU",
            entry_year_level=2,
            items=[{"course": "CMSC 14100", "term": "2027-AU", "status": "transfer"}],
            credits=[{"kind": "transfer", "label": "First-year credit elsewhere", "units": 1200}],
        ),
        {},
        "infeasible",
        "",
    ),
    (
        "transfer, Economics",
        plan(["core", "econ-ba"], entry_term="2027-AU", entry_year_level=2),
        {},
        "infeasible",
        "",
    ),
    (
        "pre-med timing",
        plan(
            ["core"],
            goals=[
                {
                    "id": "pm",
                    "type": "premed",
                    "courses": ["CHEM 10100", "CHEM 10200", "CHEM 11300"],
                    "complete_by": "Y2-SP",
                }
            ],
        ),
        {},
        "plan",
        "",
    ),
    (
        "study abroad in Paris",
        plan(
            ["core", "civ-abroad-paris-mdd"],
            goals=[
                {
                    "id": "ab",
                    "type": "study_abroad",
                    "program_id": "civ-abroad-paris-mdd",
                    "abroad_term": "Y3-AU",
                }
            ],
        ),
        {},
        "plan",
        "",
    ),
    (
        "study abroad in Cordoba",
        plan(
            ["core", "civ-abroad-cordoba"],
            goals=[
                {
                    "id": "ab",
                    "type": "study_abroad",
                    "program_id": "civ-abroad-cordoba",
                    "abroad_term": "Y3-SP",
                }
            ],
        ),
        {},
        "plan",
        "",
    ),
    (
        "graduate early: impossible",
        plan(
            ["core", "econ-ba"],
            goals=[{"id": "g", "type": "graduate_by", "by_term": "Y2-SP", "hard": True}],
        ),
        {},
        "infeasible",
        "Graduating by Spring 2028 needs",
    ),
    (
        "graduate early: one quarter",
        plan(
            ["core"], goals=[{"id": "g", "type": "graduate_by", "by_term": "Y4-WI", "hard": True}]
        ),
        {},
        "plan",
        "",
    ),
    (
        "three courses a quarter",
        plan(
            ["core", "cmsc-ba"],
            goals=[{"id": "l", "type": "course_load", "max_courses": 3, "hard": True}],
        ),
        {},
        "infeasible",
        "",
    ),
    (
        "second-year, remaining quarters",
        plan(["core", "cmsc-bs"], items=done(*Y1)),
        {"scope": "remaining", "today_term": "2027-AU"},
        "plan",
        "",
    ),
    (
        "lighter load, ML interest",
        plan(["core", "cmsc-bs"]),
        {"load": -1, "interests": ["machine learning"], "max_courses_per_term": 4},
        "plan",
        "",
    ),
    (
        "challenge me",
        plan(["core", "cmsc-bs"], goals=[{"id": "c", "type": "challenge", "min_index": 10}]),
        {"load": 1},
        "plan",
        "",
    ),
]


@pytest.mark.parametrize(
    ("name", "p", "options", "expect", "fragment"), PROFILES, ids=[p[0] for p in PROFILES]
)
def test_profile(
    world: tuple[SeedBundle, Catalog],
    name: str,
    p: PlanState,
    options: dict[str, Any],
    expect: str,
    fragment: str,
) -> None:
    bundle, catalog = world
    rules = build_rules(bundle, [x.program_id for x in p.programs])
    started = time.perf_counter()
    result = generate(p, rules, catalog, GenerateOptions(**options))
    elapsed = time.perf_counter() - started
    assert elapsed < LIMIT_S, f"{name}: {elapsed:.2f}s"
    assert result.alerts == [], result.alerts
    if result.variants:
        assert expect != "infeasible", f"{name}: expected an explanation, got a plan"
        for v in result.variants:
            report = verify(v.plan, rules, catalog)  # re-check independently of the generator
            assert report.status != "errors", [
                i.message for i in report.issues if i.level == "error"
            ]
            assert report.certificate is not None
            assert check_certificate(v.plan, rules, catalog, report.certificate)
            replay = apply_ops(p, v.ops)
            assert sorted((i.course, i.term) for i in replay.items) == sorted(
                (i.course, i.term) for i in v.plan.items
            )
    else:
        assert expect != "plan", f"{name}: no plan: {result.infeasible}"
        assert result.infeasible is not None and result.infeasible.message
        assert fragment in result.infeasible.message
        assert "time limit" not in result.infeasible.message
        assert {c.id for c in result.infeasible.conflicts} == CONFLICTS[name]
