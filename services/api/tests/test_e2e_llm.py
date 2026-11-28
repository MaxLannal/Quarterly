"""The LLM_FAKE=e2e client drives the real agents on the real seed (prompt 12 journeys)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from agent_test_support import events, of, use_llm
from api.agents.e2e_llm import e2e_llm
from api.config import Settings, get_settings
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from auth_test_support import Env, auth_env, csrf, migrated_database

pytestmark = pytest.mark.db

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"
PLAN: dict[str, Any] = {
    "catalog_year": "2026-27",
    "entry_term": "2026-AU",
    "placements": ["MATH 15100"],
    "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
}


@pytest.fixture(scope="module")
def env() -> Iterator[Env]:
    with migrated_database() as url, pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "show_unpublished_programs", True)
        with auth_env(url, mp) as e:
            with e.db() as db:
                upsert_bundle(db, load_bundle(SEED))
            use_llm(e, e2e_llm())
            yield e


def test_planner_generates_grouped_proposals_with_reasons(env: Env) -> None:
    body = {
        "mode": "generate",
        "plan": PLAN,
        "profile_answers": {"interests": ["machine learning"]},
    }
    evs = events(env.client.post("/agents/planner", json=body))
    assert of(evs, "plan") and not of(evs, "error")
    proposals = of(evs, "proposal")
    assert proposals and all(p["ops"] for p in proposals)
    # The fake explanation passed the server's checks: it names the interest and cites it.
    assert any("machine learning" in p["why"] for p in proposals)
    assert any(c["id"] == "interests" for p in proposals for c in p["citations"])
    done = {e["name"] for e in of(evs, "step") if e["status"] == "done"}
    assert {"Writing your plan", "Explaining each choice"} <= done


def test_planner_chat_answers_with_a_citation_and_a_proposal(env: Env) -> None:
    headers = csrf(env.signup("e2e-heron"))
    plan = env.client.post("/plans", json={"name": "Main", "state": PLAN}, headers=headers).json()
    body = {
        "mode": "chat",
        "plan": plan["state"],
        "plan_id": plan["id"],
        "message": "Is MATH 20700 worth it for ML?",
    }
    evs = events(env.client.post("/agents/planner", json=body, headers=headers))
    message = of(evs, "message")[-1]
    assert "MATH 20700" in message["text"]
    assert [c["id"] for c in message["citations"]] == ["MATH 20700"]
    proposal = of(evs, "proposal")[0]
    assert proposal["change_set_id"] and proposal["ops"][0]["course"] == "MATH 20700"


def test_fake_mode_is_refused_outside_development() -> None:
    prod = Settings(_env_file=None, environment="production", llm_fake="e2e")  # type: ignore[call-arg]
    assert any("LLM_FAKE" in p for p in prod.production_problems())
