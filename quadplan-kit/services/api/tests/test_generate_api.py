"""Both generate endpoints end to end on the real 2026-27 seed (prompt 06)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from api.config import get_settings
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from auth_test_support import Env, auth_env, csrf, migrated_database
from planner_core.changes import apply_ops
from planner_core.models import ChangeOp, PlanState
from pydantic import TypeAdapter

pytestmark = pytest.mark.db

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"
STATE: dict[str, Any] = {
    "catalog_year": "2026-27",
    "entry_term": "2026-AU",
    "placements": ["MATH 15100"],
    "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
}
OPS = TypeAdapter(list[ChangeOp])


@pytest.fixture(scope="module")
def env() -> Iterator[Env]:
    with migrated_database() as url, pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "show_unpublished_programs", True)
        with auth_env(url, mp) as e:
            with e.db() as db:
                upsert_bundle(db, load_bundle(SEED))
            yield e


def test_generate_for_a_browser_plan(env: Env) -> None:
    resp = env.client.post("/plans/generate", json={"plan": STATE, "options": {"variants": 2}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["infeasible"] is None and 1 <= len(body["variants"]) <= 2
    for v in body["variants"]:
        assert v["report"]["status"] != "errors" and v["report"]["certificate"] is not None
        cs = v["change_set"]
        assert cs["id"] is None and cs["status"] == "proposed" and cs["origin"] == "generate"
        replay = apply_ops(PlanState.model_validate(STATE), OPS.validate_python(cs["ops"]))
        assert len(replay.items) == len(v["plan"]["items"])
    explained = env.client.post("/plans/generate", json={"plan": {**STATE, "placements": []}})
    assert "placement result" in explained.json()["infeasible"]["message"]


def test_generate_and_apply_for_a_saved_plan(env: Env) -> None:
    headers = csrf(env.signup("calm-otter"))
    plan = env.client.post("/plans", json={"name": "Main", "state": STATE}, headers=headers).json()
    resp = env.client.post(
        f"/plans/{plan['id']}/generate?mode=deterministic", json={"variants": 1}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    variant = resp.json()["variants"][0]
    cs = variant["change_set"]
    assert cs["id"] and cs["base_plan_hash"] == plan["plan_hash"]
    stored = env.client.get(f"/plans/{plan['id']}/changesets", headers=headers).json()
    assert [c["id"] for c in stored] == [cs["id"]]
    applied = env.client.post(
        f"/plans/{plan['id']}/changesets/{cs['id']}/apply",
        json={"base_plan_hash": plan["plan_hash"]},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    state = applied.json()["state"]
    assert len(state["items"]) == len(variant["plan"]["items"])
    report = env.client.post("/verify", json={"plan": state}).json()
    assert report["status"] != "errors" and report["certificate"] is not None
