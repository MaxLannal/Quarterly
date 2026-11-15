"""The in-process year cache builds exactly what the queries build (prompt 12 performance)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from api.repo import rules as repo
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from planner_core.models import PlanState
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db
ROOT = Path(__file__).resolve().parents[3]


def test_cached_inputs_equal_the_queried_ones(migrated_db_url: str) -> None:
    engine = sa.create_engine(migrated_db_url)
    plans = json.loads((ROOT / "loadtest" / "plans.json").read_text())["plans"][:6]
    with Session(engine) as db:
        upsert_bundle(db, load_bundle(ROOT / "data" / "seed" / "2026-27"))
        db.commit()
        repo.clear_rules_cache()
        for raw in plans:
            plan = PlanState.model_validate(raw)
            for kwargs in ({}, {"whole_catalog": True}, {"section_terms": ["2027-WI"]}):
                queried = repo.load_verify_inputs(db, plan, show_unpublished=True, **kwargs)
                cached = repo.load_verify_inputs_cached(
                    db, plan, ttl=60, show_unpublished=True, **kwargs
                )
                for a, b in zip(queried, cached, strict=True):
                    assert a.model_dump(mode="json") == b.model_dump(mode="json")
        # A stale copy is served while one background refresh reloads it.
        before = repo._year(db, "2026-27", ttl=60)
        again = repo._year(db, "2026-27", ttl=0)  # stale: same copy back, refresh started
        assert again is before
        repo.clear_rules_cache()
        assert repo.preload_rules_cache(db) >= 1 and repo._years
        repo.clear_rules_cache()
        assert not repo._years
    engine.dispose()
