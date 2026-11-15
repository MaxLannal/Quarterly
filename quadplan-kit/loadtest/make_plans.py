"""Build realistic full plans for the load test from the real 2026-27 seed (no API, no LLM).

    uv run python loadtest/make_plans.py   # writes loadtest/plans.json
"""

from __future__ import annotations

import json
from pathlib import Path

from api.seed.bundle import build_catalog, build_rules, load_bundle
from planner_core.generator import generate
from planner_core.models import GenerateOptions, PlanState

ROOT = Path(__file__).resolve().parents[1]
COMBOS = [["core", "cmsc-bs"], ["core", "cmsc-ba"], ["core", "math-bs"], ["core", "econ-ba"], ["core", "math-ba"]]


def main() -> None:
    bundle = load_bundle(ROOT / "data" / "seed" / "2026-27")
    catalog = build_catalog(bundle)
    plans = []
    for programs in COMBOS:
        state = PlanState.model_validate(
            {
                "catalog_year": "2026-27",
                "entry_term": "2026-AU",
                "placements": ["MATH 15100"],
                "programs": [{"program_id": p} for p in programs],
            }
        )
        result = generate(state, build_rules(bundle, programs), catalog, GenerateOptions(variants=3))
        plans += [v.plan.model_dump(mode="json") for v in result.variants]
    electives = sorted({c.code for c in catalog.courses if c.code.split(" ")[1] < "30000"})[:300]
    out = {"plans": plans, "electives": electives}
    (ROOT / "loadtest" / "plans.json").write_text(json.dumps(out))
    print(f"wrote {len(plans)} plans and {len(electives)} electives")


if __name__ == "__main__":
    main()
