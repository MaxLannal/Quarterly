"""The requirements brief the planner agent plans from, built from the 2026-27 seed (no DB)."""

from __future__ import annotations

from pathlib import Path

import pytest
from api.agents.planner.brief import known_codes, requirements_brief
from api.seed.bundle import build_catalog, build_rules, load_bundle
from planner_core import verify_checked
from planner_core.models import Catalog, OfferingPattern, PlanState, RuleSet

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"


@pytest.fixture(scope="module")
def seed() -> tuple[RuleSet, Catalog]:
    bundle = load_bundle(SEED)
    return build_rules(bundle), build_catalog(bundle)


def cs_first_year(**extra: object) -> PlanState:
    return PlanState.model_validate(
        {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
            **extra,
        }
    )


def brief_of(seed: tuple[RuleSet, Catalog], state: PlanState) -> str:
    rules, catalog = seed
    report, _ = verify_checked(state, rules, catalog)
    return requirements_brief(state, rules, catalog, report)


def test_brief_lists_unmet_nodes_with_offered_quarters(seed: tuple[RuleSet, Catalog]) -> None:
    rules, catalog = seed
    # The quarters come from the catalog's offering data (the DB adds it), never from a model.
    pattern = OfferingPattern(course="CMSC 14100", quarter="AU", p_offered=0.9)
    with_offering = catalog.model_copy(update={"offerings": [pattern]})
    state = cs_first_year()
    report, _ = verify_checked(state, rules, with_offering)
    text = requirements_brief(state, rules, with_offering, report)
    assert "## cmsc-bs" in text and "## core" in text
    assert "CMSC 14100 [AU]" in text
    assert "CMSC 14200 [no offering data]" in text
    assert "TRNC 10100" not in text  # credit-only courses are never candidates


def test_brief_skips_met_nodes(seed: tuple[RuleSet, Catalog]) -> None:
    before = brief_of(seed, cs_first_year())
    done = [
        {"course": c, "term": t, "status": "completed"}
        for c, t in (
            ("CMSC 14100", "2025-AU"),
            ("CMSC 14200", "2026-WI"),
            ("CMSC 14300", "2026-SP"),
            ("CMSC 14400", "2026-SP"),
        )
    ]
    after = brief_of(seed, cs_first_year(entry_term="2025-AU", items=done))
    assert "CMSC 14100 [" in before and "CMSC 14100 [" not in after


def test_known_codes_has_the_catalog_and_the_plan(seed: tuple[RuleSet, Catalog]) -> None:
    _, catalog = seed
    codes = known_codes(cs_first_year(), catalog)
    assert {"CMSC 14100", "MATH 15100"} <= codes and "CMSC 99999" not in codes
