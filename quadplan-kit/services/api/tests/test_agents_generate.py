"""A1 plan generator over SSE (prompt 07) on the real 2026-27 seed, with FakeLLM only:
fallbacks without an LLM, budget exhaustion, one repair turn, rationale checks, citations,
saved plans and the daily limits."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from agent_test_support import events, of, use_llm
from api.agents import generate as gen
from api.config import get_settings
from api.db import models as m
from api.repo.rules import load_verify_inputs
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from auth_test_support import Env, auth_env, csrf, migrated_database
from llm_gateway.api import FakeLLM, ToolCall, get_llm
from planner_core import verify_checked
from planner_core.changes import apply_ops
from planner_core.generator import horizon
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
CODE = re.compile(r"\b[A-Z]{2,5} \d{5}\b")


@pytest.fixture(scope="module")
def env() -> Iterator[Env]:
    with migrated_database() as url, pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "show_unpublished_programs", True)
        with auth_env(url, mp) as e:
            with e.db() as db:
                upsert_bundle(db, load_bundle(SEED))
            yield e


@pytest.fixture(autouse=True)
def fresh_limits(env: Env) -> Iterator[None]:
    env.redis.flushall()
    env.app.dependency_overrides.pop(get_llm, None)
    yield


def request(**extra: Any) -> dict[str, Any]:
    return {"plan": STATE, "variants": 1, "interests": ["machine learning"], **extra}


def steps(evs: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(e["name"], e["status"]) for e in of(evs, "step")]


def rationale_answer(user_text: str, *, tamper: str | None = None) -> dict[str, Any]:
    """A rationale for every variant and quarter the prompt lists (as a model would write)."""
    variants: list[dict[str, Any]] = []
    for line in user_text.splitlines():
        if line.startswith("Option "):
            variants.append({"label": line.split(" (")[0].rstrip(":"), "quarters": []})
        elif line.startswith("- ") and variants:
            term = line[2:9]
            courses = sorted(set(CODE.findall(line.split(": ", 1)[1])))
            if tamper == variants[-1]["label"] and not variants[-1]["quarters"]:
                courses = [*courses, "MATH 99999"]
            variants[-1]["quarters"].append(
                {
                    "term": term,
                    "courses": courses,
                    "text": f"Builds toward the major with {len(courses)} courses.",
                    "citations": [f"course:{courses[0]}", "course:FAKE 99999", "post:12"],
                }
            )
    return {"variants": variants}


def scripted_rationale(fake: FakeLLM, *, tamper: str | None = None, invalid: bool = False) -> None:
    """Answers the rationale run from its own prompt (the script cannot know the variants)."""

    def hook(call: dict[str, Any]) -> None:
        if "You explain generated course plans" in call["system"] and len(call["messages"]) == 1:
            answer = rationale_answer(call["messages"][0]["content"], tamper=tamper)
            if invalid:
                long_text = " ".join(["word"] * 40)
                for v in answer["variants"]:
                    v["quarters"][0]["text"] = long_text
                fake.script["a1_plan_generator"] += [ToolCall("submit_rationale", answer)] * 2
            else:
                fake.script["a1_plan_generator"].append(ToolCall("submit_rationale", answer))

    fake.on_call = hook


def test_without_an_llm_the_fallbacks_still_generate_verified_plans(env: Env) -> None:
    headers = csrf(env.signup("calm-otter"))
    plan = env.client.post("/plans", json={"name": "Main", "state": STATE}, headers=headers).json()
    evs = events(
        env.client.post(
            "/agents/generate",
            json=request(plan=plan["state"], plan_id=plan["id"]),
            headers=headers,
        )
    )
    assert steps(evs) == [
        (gen.STEP_LOAD, "started"),
        (gen.STEP_LOAD, "done"),
        (gen.STEP_ELECTIVES, "started"),
        (gen.STEP_ELECTIVES, "failed"),
        (gen.STEP_DEFAULT, "done"),
        (gen.STEP_SOLVE, "started"),
        (gen.STEP_SOLVE, "done"),
        (gen.STEP_VERIFY, "started"),
        (gen.STEP_VERIFY, "done"),
        (gen.STEP_RATIONALE, "started"),
        (gen.STEP_RATIONALE, "failed"),
    ]
    (variant,) = of(evs, "variant")
    assert variant["rationale"] == {} and variant["citations"] == []
    assert variant["report"]["certificate"] is not None
    cs = variant["change_set"]
    assert cs["id"] and cs["base_plan_hash"] == plan["plan_hash"]  # stored: a saved plan
    applied = env.client.post(
        f"/plans/{plan['id']}/changesets/{cs['id']}/apply",
        json={"base_plan_hash": plan["plan_hash"]},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    run_id = of(evs, "done")[0]["run_id"]
    with env.db() as db:
        run = db.get(m.AgentRun, uuid.UUID(run_id))
        assert run is not None and run.status == "fallback" and run.kind == "generate"


def test_agent_preferences_and_rationale_with_checked_citations(env: Env) -> None:
    with env.db() as db:
        state = PlanState.model_validate(STATE)
        rules, catalog = load_verify_inputs(
            db, state, show_unpublished=True, whole_catalog=True, section_terms=horizon(state)
        )
        report, _ = verify_checked(state, rules, catalog)
        nodes = gen.choice_nodes(state, rules, catalog, report, ["machine learning"])
    assert nodes, "the CS major has electives to choose"
    node = nodes[0]
    picks = [
        {"code": c, "score": 90 - i, "reason": "Matches your interest."}
        for i, c in enumerate(node.candidates[:3])
    ]
    fake = FakeLLM(
        script={
            "a1_plan_generator": [
                ToolCall(
                    "search_courses",
                    {
                        "query": "machine learning",
                        "subject": None,
                        "level": None,
                        "quarter": None,
                        "core_tag": None,
                        "max_workload_hours": None,
                    },
                ),
                # A code that cannot fill the requirement: repaired once.
                ToolCall(
                    "submit_preferences",
                    {
                        "nodes": [
                            {
                                "node_id": node.id,
                                "picks": [
                                    *picks,
                                    {"code": "MATH 99999", "score": 1, "reason": "x"},
                                ],
                            }
                        ]
                    },
                ),
                ToolCall("submit_preferences", {"nodes": [{"node_id": node.id, "picks": picks}]}),
            ]
        }
    )
    scripted_rationale(fake, tamper="Option B")
    use_llm(env, fake)
    evs = events(env.client.post("/agents/generate", json=request(variants=2)))
    assert (gen.STEP_ELECTIVES, "done") in steps(evs)
    assert (gen.STEP_RATIONALE, "done") in steps(evs)
    repair = fake.calls[2]["messages"][-1]["content"][0]
    assert repair["is_error"] and "MATH 99999 cannot fill" in repair["content"]
    variants = of(evs, "variant")
    assert len(variants) == 2
    a, b = variants
    assert a["rationale"] and all(len(t.split()) <= 25 for t in a["rationale"].values())
    # Only ids the run actually saw survive: the variant's own courses, not FAKE 99999/post:12.
    assert a["citations"] and {c["kind"] for c in a["citations"]} == {"course"}
    assert all(c["id"] != "FAKE 99999" for c in a["citations"])
    # Option B's rationale changed its course set, so it was discarded; the plan is kept.
    assert b["rationale"] == {} and b["report"]["certificate"] is not None
    replay = apply_ops(PlanState.model_validate(STATE), OPS.validate_python(a["change_set"]["ops"]))
    assert replay.items
    assert a["change_set"]["id"] is None  # a browser plan: nothing stored
    with env.db() as db:
        calls = db.scalars(sa.select(m.LlmCall)).all()
        versions = {c.prompt_version for c in calls}
        assert versions == {"a1_preferences@1", "a1_rationale@1"}


def test_budget_exhaustion_and_a_failed_repair_take_the_fallbacks(env: Env) -> None:
    search = ToolCall("get_course", {"code": "CMSC 14100"})
    fake = FakeLLM(script={"a1_plan_generator": [search] * 13})
    scripted_rationale(fake, invalid=True)
    use_llm(env, fake)
    evs = events(env.client.post("/agents/generate", json=request()))
    assert (gen.STEP_ELECTIVES, "failed") in steps(evs)
    assert (gen.STEP_DEFAULT, "done") in steps(evs)
    assert (gen.STEP_RATIONALE, "failed") in steps(evs)
    (variant,) = of(evs, "variant")
    assert variant["rationale"] == {} and variant["report"]["certificate"] is not None
    # 12 tool calls were allowed; the 13th ended the run.
    pref_calls = [c for c in fake.calls if "You choose electives" in c["system"]]
    assert len(pref_calls) == 13


def test_an_impossible_request_is_explained(env: Env) -> None:
    evs = events(
        env.client.post("/agents/generate", json=request(plan={**STATE, "placements": []}))
    )
    infeasible = of(evs, "infeasible")
    assert infeasible and "placement result" in infeasible[0]["message"]
    assert not of(evs, "variant") and of(evs, "done")


def test_daily_limits(env: Env) -> None:
    bad = {**STATE, "programs": [{"program_id": "nope"}]}
    for _ in range(3):
        resp = env.client.post("/agents/generate", json=request(plan=bad))
        assert resp.status_code == 422
    assert env.client.post("/agents/generate", json=request(plan=bad)).status_code == 429
    # The counter lives only in Redis, keyed by a hash, with a TTL of at most a day.
    keys = env.redis.keys("rl:agent-generate:ip:*")
    assert len(keys) == 1 and 0 < env.redis.ttl(keys[0]) <= 24 * 3600
    assert "127.0.0.1" not in keys[0] and "testclient" not in keys[0]

    headers = csrf(env.signup("busy-otter"))
    for _ in range(10):
        resp = env.client.post("/agents/generate", json=request(plan=bad), headers=headers)
        assert resp.status_code == 422
    over = env.client.post("/agents/generate", json=request(plan=bad), headers=headers)
    assert over.status_code == 429


def test_a_foreign_plan_id_is_not_found(env: Env) -> None:
    headers = csrf(env.signup("nosy-otter"))
    resp = env.client.post(
        "/agents/generate",
        json=request(plan_id="00000000-0000-0000-0000-000000000000"),
        headers=headers,
    )
    assert resp.status_code == 404
