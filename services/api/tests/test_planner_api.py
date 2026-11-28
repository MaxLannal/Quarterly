"""POST /agents/planner and its neighbours (issues #17 and #18) on the fake 2099-00 fixture:
the rate limits, proposals that re-base onto later edits, and answers that wait on the
dashboard as profile proposals."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from agent_test_support import events, of, use_llm
from api.auth.ratelimit import DAY, Limit
from api.config import get_settings
from api.db import models as m
from api.routers import agents as agents_router
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from auth_test_support import Env, auth_env, csrf, migrated_database
from llm_gateway.api import FakeLLM, ToolCall

pytestmark = pytest.mark.db

STATE: dict[str, Any] = {
    "catalog_year": "2099-00",
    "entry_term": "2099-AU",
    "programs": [{"program_id": "test-bs"}],
    "items": [
        {"course": "TEST 10000", "term": "2099-AU"},
        {"course": "TEST 10100", "term": "2100-WI"},
    ],
}
IN_SCOPE = {"label": "in_scope", "escalate": False}


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    monkeypatch.setattr(get_settings(), "show_unpublished_programs", True)
    with auth_env(db_url, monkeypatch) as e:
        with e.db() as db:
            upsert_bundle(db, load_bundle(FIXTURES / "seed" / "2099-00"))
        yield e


def post(env: Env, body: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    return env.client.post("/agents/planner", json=body, headers=headers or {})


def add_op(course: str, term: str) -> dict[str, Any]:
    return {"op": "add", "course": course, "term": term, "from_term": None, "to_term": None}


def proposing(env: Env, *courses: str) -> None:
    calls = [
        ToolCall(
            "propose_change_set",
            {"ops": [add_op(c, "2100-SP")], "title": f"Add {c}", "kind": "elective", "why": "x"},
        )
        for c in courses
    ]
    use_llm(
        env,
        FakeLLM(
            script={
                "a2_scope_classifier": [IN_SCOPE],
                "a1_planner_chat": [
                    calls,
                    ToolCall("submit_answer", {"text": "ok", "citations": []}),
                ],
            }
        ),
    )


def saved(env: Env) -> tuple[dict[str, str], dict[str, Any]]:
    headers = csrf(env.signup("quiet-heron"))
    resp = env.client.post("/plans", json={"name": "Main", "state": STATE}, headers=headers)
    assert resp.status_code == 201, resp.text
    return headers, resp.json()


def chat_proposals(
    env: Env, headers: dict[str, str], plan: dict[str, Any], *courses: str
) -> list[str]:
    proposing(env, *courses)
    body = {
        "mode": "chat",
        "plan": plan["state"],
        "plan_id": plan["id"],
        "message": "Add electives",
    }
    return [p["change_set_id"] for p in of(events(post(env, body, headers)), "proposal")]


def apply(env: Env, headers: dict[str, str], plan: dict[str, Any], cs: str, base: str) -> Any:
    return env.client.post(
        f"/plans/{plan['id']}/changesets/{cs}/apply", json={"base_plan_hash": base}, headers=headers
    )


def test_a_resume_is_not_a_new_generation(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents_router, "GENERATE_PER_IP", Limit("agent-generate:ip", 1, DAY))
    first = events(post(env, {"mode": "generate", "plan": STATE}))
    question = of(first, "question")[0]
    assert question["field"] == "interests"
    idle = ToolCall("submit_repair", {"summary": "x", "ops": [], "bent": []})
    fill = ToolCall(
        "submit_plan",
        {
            "groups": [
                {
                    "id": "g1",
                    "title": "Test sequence",
                    "kind": "major",
                    "courses": [
                        {"code": "TEST 10000", "term": "2099-AU"},
                        {"code": "TEST 10100", "term": "2100-WI"},
                        {"code": "TEST 20200", "term": "2100-SP"},
                    ],
                    "why": "x",
                    "rules": [],
                }
            ],
            "notes": "",
        },
    )
    explain = ToolCall(
        "submit_explanations", {"groups": [{"id": "g1", "why": "For testing.", "citations": []}]}
    )
    questions = ToolCall("submit_questions", {"questions": []})
    use_llm(env, FakeLLM(script={"a1_planner_agent": [questions, fill, idle, idle, idle, explain]}))
    resumed = post(
        env,
        {
            "mode": "generate",
            "plan": STATE,
            "run_id": question["run_id"],
            "answer": {"question_id": "interests", "text": "software testing"},
        },
    )
    evs = events(resumed)
    assert of(evs, "plan") and of(evs, "proposal")
    assert of(evs, "done")[0]["profile_answers"] == {"interests": ["Software testing"]}
    assert post(env, {"mode": "generate", "plan": STATE}).status_code == 429


def test_planner_change_sets_apply_out_of_order(env: Env) -> None:
    headers, plan = saved(env)
    first, second = chat_proposals(env, headers, plan, "TEST 20200", "TEST 20300")
    ok = apply(env, headers, plan, second, plan["plan_hash"])
    assert ok.status_code == 200, ok.text
    # The plan moved on; the other proposal of the same run still fits, so it re-bases.
    again = apply(env, headers, plan, first, plan["plan_hash"])
    assert again.status_code == 200, again.text
    items = {i["course"]: i for i in again.json()["state"]["items"]}
    assert items["TEST 20200"]["locked"] and items["TEST 20300"]["locked"]  # issue #18 step 13
    assert not items["TEST 10000"]["locked"]


def test_planner_change_set_goes_stale_when_course_added_by_hand(env: Env) -> None:
    headers, plan = saved(env)
    (cs,) = chat_proposals(env, headers, plan, "TEST 20200")
    moved = env.client.patch(
        f"/plans/{plan['id']}/items",
        json={
            "base_plan_hash": plan["plan_hash"],
            "ops": [{"op": "add", "course": "TEST 20200", "term": "2100-SP"}],
        },
        headers=headers,
    )
    assert moved.status_code == 200, moved.text
    resp = apply(env, headers, plan, cs, moved.json()["plan_hash"])
    assert (
        resp.status_code == 409
        and resp.json()["detail"] == "This proposal no longer fits your plan."
    )
    with env.db() as db:
        assert db.get(m.ChangeSet, uuid.UUID(cs)).status == "stale"


def test_profile_proposals_wait_for_the_student(env: Env) -> None:
    headers = csrf(env.signup("quiet-heron"))
    bad = env.client.post(
        "/me/profile/proposals", json={"field": "email", "value": "x"}, headers=headers
    )
    assert bad.status_code == 422
    made = env.client.post(
        "/me/profile/proposals", json={"field": "interests", "value": ["robotics"]}, headers=headers
    )
    assert made.status_code == 201 and made.json()["source"] == "import"
    other = env.client.post(
        "/me/profile/proposals", json={"field": "pace", "value": "early"}, headers=headers
    ).json()
    listed = env.client.get("/me/profile/proposals", headers=headers).json()
    assert {p["field"] for p in listed} == {"interests", "pace"}
    accepted = env.client.post(f"/me/profile/proposals/{made.json()['id']}/accept", headers=headers)
    assert accepted.status_code == 200 and accepted.json()["interests"] == ["robotics"]
    assert (
        env.client.post(f"/me/profile/proposals/{other['id']}/reject", headers=headers).status_code
        == 204
    )
    assert env.client.get("/me/profile", headers=headers).json()["pace"] is None
    assert env.client.get("/me/profile/proposals", headers=headers).json() == []
    again = env.client.post(f"/me/profile/proposals/{other['id']}/accept", headers=headers)
    assert again.status_code == 409
    browser = env.browser()
    them = csrf(env.signup("loud-heron", client=browser))
    stolen = browser.post(f"/me/profile/proposals/{made.json()['id']}/accept", headers=them)
    assert stolen.status_code == 404
    with env.db() as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(m.ProfileProposal)) == 2


def test_old_agent_routes_are_gone(env: Env) -> None:
    assert env.client.post("/agents/generate", json={"plan": STATE}).status_code == 404
    assert env.client.post("/agents/chat", json={"plan": STATE, "message": "hi"}).status_code == 404


def test_another_accounts_plan_is_not_found(env: Env) -> None:
    _, plan = saved(env)
    browser = env.browser()
    them = csrf(env.signup("loud-heron", client=browser))
    body = {"mode": "chat", "plan": STATE, "plan_id": plan["id"], "message": "hi"}
    assert browser.post("/agents/planner", json=body, headers=them).status_code == 404
    assert env.browser().post("/agents/planner", json=body).status_code == 404  # logged out


def test_planner_add_goes_stale_when_the_course_is_in_another_quarter(env: Env) -> None:
    """Final review 1: a re-based add must not put a course in the plan twice."""
    headers, plan = saved(env)
    (cs,) = chat_proposals(env, headers, plan, "TEST 20200")
    by_hand = {"op": "add", "course": "TEST 20200", "term": "2100-WI"}
    moved = env.client.patch(
        f"/plans/{plan['id']}/items",
        json={"base_plan_hash": plan["plan_hash"], "ops": [by_hand]},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text
    resp = apply(env, headers, plan, cs, moved.json()["plan_hash"])
    assert resp.status_code == 409
    courses = [
        i["course"]
        for i in env.client.get(f"/plans/{plan['id']}", headers=headers).json()["state"]["items"]
    ]
    assert courses.count("TEST 20200") == 1


def test_an_abandoned_question_does_not_keep_its_state(env: Env) -> None:
    """Final review 3: a paused run's state (a logged-out student's answers) goes after a day,
    even when nobody resumes it."""
    import datetime as dt

    from api.agents.planner.chat import purge_old_history

    with env.db() as db:
        old = m.AgentRun(kind="planner", plan_id=None, model="x", status="waiting",
                         created_day=dt.date.today() - dt.timedelta(days=3),
                         state={"phase": "ask", "day": "2000-01-01"})  # fmt: skip
        new = m.AgentRun(kind="planner", plan_id=None, model="x", status="waiting",
                         created_day=dt.date.today(), state={"phase": "ask", "day": "2099-01-01"})  # fmt: skip
        db.add_all([old, new])
        db.commit()
        purge_old_history(db)
        db.commit()
        assert db.get(m.AgentRun, old.id).state is None
        assert db.get(m.AgentRun, new.id).state is not None
