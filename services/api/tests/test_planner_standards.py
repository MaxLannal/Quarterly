"""The student's standards that the planner checks itself (plan-guideline G14-G16)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from api.agents.planner.standards import (
    Standards,
    preference_line,
    standard_issues,
    standards_from,
)
from api.seed.bundle import build_catalog, load_bundle
from planner_core.models import Catalog, PlanState

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return build_catalog(load_bundle(SEED))


def plan(items: list[tuple[str, str]]) -> PlanState:
    return PlanState.model_validate(
        {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "items": [{"course": c, "term": t} for c, t in items],
        }
    )


def test_standards_from_the_record() -> None:
    notes = "- 2026-11-20 · prefer · more theory\n" + preference_line(
        dt.date(2026, 11, 26),
        "avoid",
        "I hate Language and the Human",
        ["HUMA 12000", "HUMA 12100"],
    )
    s = standards_from(
        {"terms_away": [{"term": "2027-AU", "kind": "abroad"}], "course_load": "normal"}, notes
    )
    assert s == Standards(
        away_terms=frozenset({"2027-AU"}),
        max_units=400,
        avoid=frozenset({"HUMA 12000", "HUMA 12100"}),
    )
    assert standards_from({"course_load": "ambitious"}, None).max_units is None
    assert standards_from({}, None) == Standards(frozenset(), None, frozenset())


def test_preference_line_format() -> None:
    line = preference_line(dt.date(2026, 11, 26), "avoid", "  no early\nclasses ", ["cmsc 14100"])
    assert line == "- 2026-11-26 · avoid · no early classes [CMSC 14100]"
    assert preference_line(dt.date(2026, 11, 26), "prefer", "theory", []) == (
        "- 2026-11-26 · prefer · theory"
    )


def test_standard_issues_away_load_avoid(catalog: Catalog) -> None:
    s = Standards(away_terms=frozenset({"2027-AU"}), max_units=400, avoid=frozenset({"MATH 15100"}))
    five = [("CMSC 14100", "2026-AU"), ("MATH 15100", "2026-AU"), ("PHYS 13100", "2026-AU")]
    five += [("CHEM 11100", "2026-AU"), ("ECON 20000", "2026-AU"), ("CMSC 14200", "2027-AU")]
    issues = standard_issues(plan(five), catalog, s)
    by_code = {i.code: i for i in issues}
    assert set(by_code) == {"S01", "S02", "S03"}
    assert by_code["S01"].course_ids == ["CMSC 14200"] and by_code["S01"].term_ids == ["2027-AU"]
    assert by_code["S02"].term_ids == ["2026-AU"]
    assert by_code["S03"].course_ids == ["MATH 15100"]
    assert all(i.level == "error" for i in issues)


def test_completed_courses_are_not_standard_issues(catalog: Catalog) -> None:
    s = Standards(
        away_terms=frozenset({"2026-AU"}), max_units=None, avoid=frozenset({"CMSC 14100"})
    )
    state = PlanState.model_validate(
        {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "items": [{"course": "CMSC 14100", "term": "2026-AU", "status": "completed"}],
        }
    )
    assert standard_issues(state, catalog, s) == []
