"""FEEDBACK 2026-11-14: Summer belongs to the academic year it opens (before Autumn); the plan
ends at its graduation quarter (years left for transfers, more years, or graduating early)."""

import pytest
from planner_core.generator import graduation_term, horizon
from planner_core.hashing import plan_hash
from planner_core.models import PlanState
from planner_core.terms import QUARTERS, academic_year, resolve_term_ref, term_at, year_index
from pydantic import ValidationError


def plan(**extra: object) -> PlanState:
    return PlanState.model_validate({"catalog_year": "2026-27", "entry_term": "2026-AU", **extra})


def test_summer_opens_the_academic_year() -> None:
    assert QUARTERS == ("SU", "AU", "WI", "SP")
    assert academic_year("2026-SU") == academic_year("2026-AU") == academic_year("2027-SP") == 2026
    assert academic_year("2027-SU") == 2027  # the summer after spring is next year's
    assert term_at("2026-AU", 1, "SU") == "2026-SU"
    assert term_at("2026-AU", 2, "SU") == "2027-SU"
    assert resolve_term_ref("Y1-SU", "2026-AU") == "2026-SU"
    assert year_index("2026-SU", "2026-AU") == 1


def test_years_left_and_graduation_quarter() -> None:
    first_year = plan()
    assert graduation_term(first_year) == "2030-SP"
    assert len(horizon(first_year)) == 12 and "2030-SU" not in horizon(first_year)
    transfer = plan(entry_year_level=2)  # three years left
    assert graduation_term(transfer) == "2029-SP" and len(horizon(transfer)) == 9
    early = plan(graduation_term="2030-WI")  # graduating in Winter of year 4
    assert horizon(early)[-1] == "2030-WI" and len(horizon(early)) == 11
    fifth = plan(graduation_term="2031-SP")
    assert len(horizon(fifth)) == 15


def test_graduation_quarter_is_checked_and_does_not_change_old_hashes() -> None:
    with pytest.raises(ValidationError, match="Summer"):
        plan(graduation_term="2030-SU")
    with pytest.raises(ValidationError, match="before entry_term"):
        plan(graduation_term="2026-SP")
    assert plan_hash(plan()) == plan_hash(plan(graduation_term=None))
    assert plan_hash(plan()) != plan_hash(plan(graduation_term="2030-WI"))
