"""TRNC 10100, transfer general credit (Richard, FEEDBACK "Minor issues", 2026-11-16): in the
catalog, repeatable, never offered, part of no program or the Core; transfer credits mapped to
it count toward the total units."""

from pathlib import Path

from api.seed.bundle import build_catalog, build_rules, load_bundle
from planner_core import verify
from planner_core.models import PlanState

YEAR = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"


def test_trnc_10100_is_in_the_catalog_as_transfer_general_credit() -> None:
    bundle = load_bundle(YEAR)
    trnc = next(c for c in bundle.courses if c.code == "TRNC 10100")
    assert trnc.title == "Transfer General Credit"
    assert trnc.repeatable and trnc.units == 100
    assert trnc.core_tags == [] and trnc.terms_offered == []
    assert "every transfer student will receive" in trnc.source.quote
    # No program names it: it counts as a course for no program.
    for path in (YEAR / "programs").glob("*.yaml"):
        assert "TRNC" not in path.read_text(), path.name


def test_transfer_credits_mapped_to_trnc_count_toward_total_units_only() -> None:
    bundle = load_bundle(YEAR)
    catalog = build_catalog(bundle)
    rules = build_rules(bundle, ["cmsc-bs"])
    base = {"catalog_year": "2026-27", "entry_term": "2026-AU"}
    credits = [
        {
            "kind": "transfer",
            "label": "Community college course 1",
            "maps_to": "TRNC 10100",
            "units": 100,
        },
        {
            "kind": "transfer",
            "label": "Community college course 2",
            "maps_to": "TRNC 10100",
            "units": 100,
        },
    ]

    def total(plan: dict[str, object]) -> tuple[int, int]:
        report = verify(PlanState.model_validate(plan), rules, catalog)
        row = next(p for p in report.progress if p.node_id == "college/total_units")
        program = sum(len(p.courses) for p in report.progress if p.program_id == "cmsc-bs")
        return row.have, program

    without, program_before = total({**base, "programs": [{"program_id": "cmsc-bs"}]})
    with_trnc, program_after = total(
        {**base, "programs": [{"program_id": "cmsc-bs"}], "credits": credits}
    )
    assert with_trnc == without + 200
    assert program_after == program_before  # fills nothing in the major
