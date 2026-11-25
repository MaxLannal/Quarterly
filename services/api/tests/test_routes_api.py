"""Routes on the dashboard (`/me/routes`) and the route drafter (`POST /agents/routes`), with
FakeLLM only: unknown course codes dropped, one chosen route, keeping options open, ownership,
the limit, the live steps and the rule-built routes without a model."""

from __future__ import annotations

from typing import Any

import pytest
from agent_test_support import events, of, use_llm
from api.agents import routes as routes_mod
from api.db import models as m
from auth_test_support import Env
from llm_gateway.api import FakeLLM, ToolCall
from test_profile_support import COURSES, account_id, db_url_fixture, env_fixture, login  # noqa: F401

pytestmark = pytest.mark.db


def route(title: str = "Physics first", **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "tagline": "Mechanics, then the quantum",
        "kind": "major",
        "program_ids": ["phys-bs", "made-up-ba"],
        "courses": [
            {"code": "phys13100", "title": "ignored", "year": 1, "quarter": "AU", "role": "major"},
            {"code": "PHYS 99999", "year": 2, "role": "major"},
            {"code": "HUMA 12050", "year": 1, "role": "humanities", "note": "Greek tragedy"},
            {"code": "PHYS 13100", "year": 2, "role": "major"},
        ],
        "milestones": [{"when": "Year 2, Spring", "text": "Ask about summer research"}],
        "fit": {"interests": 0.8, "career": 0.6, "humanities": 0.7, "workload": "balanced"},
        "origin": "ai",
        **extra,
    }
    return body


def create(env: Env, headers: dict[str, str], body: dict[str, Any] | None = None) -> Any:
    resp = env.client.post("/me/routes", json=body or route(), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def set_status(env: Env, headers: dict[str, str], route_id: str, status: str) -> Any:
    resp = env.client.patch(f"/me/routes/{route_id}", json={"status": status}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ------------------------------------------------------------------------------ CRUD


def test_unknown_codes_and_programs_are_dropped_and_titles_come_from_the_catalog(env: Env) -> None:
    headers = login(env)
    out = create(env, headers)
    assert [c["code"] for c in out["courses"]] == ["PHYS 13100", "HUMA 12050"]
    assert out["courses"][0]["title"] == "Mechanics"
    # The usual quarters come from the catalog's offering patterns (what was sent is replaced).
    assert out["courses"][0]["offered"] == ["AU"] and out["courses"][1]["offered"] == ["AU"]
    assert out["program_ids"] == ["phys-bs"]
    assert out["programs"] == [{"id": "phys-bs", "name": "Physics (BS)"}]
    assert out["status"] == "open" and out["origin"] == "ai" and out["position"] == 0
    listed = env.client.get("/me/routes").json()
    assert [r["id"] for r in listed["items"]] == [out["id"]] and listed["chosen_id"] is None


def test_one_chosen_route_and_keeping_options_open(env: Env) -> None:
    headers = login(env)
    a = create(env, headers, route("A"))
    b = create(env, headers, route("B"))
    assert set_status(env, headers, a["id"], "chosen")["status"] == "chosen"
    assert set_status(env, headers, b["id"], "chosen")["status"] == "chosen"
    listed = env.client.get("/me/routes").json()
    statuses = {r["title"]: r["status"] for r in listed["items"]}
    assert statuses == {"A": "open", "B": "chosen"} and listed["chosen_id"] == b["id"]
    # "Keep my options open": the chosen route goes back to open; nothing is chosen.
    set_status(env, headers, b["id"], "open")
    listed = env.client.get("/me/routes").json()
    assert listed["chosen_id"] is None
    assert {r["status"] for r in listed["items"]} == {"open"}
    archived = set_status(env, headers, a["id"], "archived")
    assert archived["status"] == "archived"
    assert set_status(env, headers, a["id"], "open")["status"] == "open"


def test_rename_note_position_and_delete(env: Env) -> None:
    headers = login(env)
    a = create(env, headers)
    resp = env.client.patch(
        f"/me/routes/{a['id']}",
        json={"title": "  My  physics  ", "note": "Ask about PHYS 23410", "position": 5},
        headers=headers,
    )
    out = resp.json()
    assert out["title"] == "My physics" and out["note"] == "Ask about PHYS 23410"
    assert out["position"] == 5 and out["tagline"] == "Mechanics, then the quantum"
    assert (
        env.client.patch(f"/me/routes/{a['id']}", json={"title": ""}, headers=headers).status_code
        == 422
    )
    assert env.client.delete(f"/me/routes/{a['id']}", headers=headers).status_code == 204
    assert env.client.get("/me/routes").json()["items"] == []
    assert env.client.delete(f"/me/routes/{a['id']}", headers=headers).status_code == 404


def test_another_accounts_route_is_404(env: Env) -> None:
    headers = login(env, "quiet-heron")
    mine = create(env, headers)
    other = env.browser()
    other_headers = login(env, "loud-crow", client=other)
    url = f"/me/routes/{mine['id']}"
    assert other.patch(url, json={"status": "chosen"}, headers=other_headers).status_code == 404
    assert other.delete(url, headers=other_headers).status_code == 404
    assert other.get("/me/routes").json()["items"] == []
    assert env.client.get("/me/routes").json()["items"][0]["status"] == "open"


def test_at_most_twelve_routes(env: Env) -> None:
    headers = login(env)
    for i in range(12):
        create(env, headers, route(f"Route {i}"))
    resp = env.client.post("/me/routes", json=route("One too many"), headers=headers)
    assert resp.status_code == 409


def test_route_validation(env: Env) -> None:
    headers = login(env)
    bad = [
        route(title=""),
        route(title="x" * 81),
        route(kind="minor"),
        route(courses=[{"code": "PHYS 13100", "year": 5}]),
        route(courses=[{"code": "PHYS 13100", "year": 1, "quarter": "FA"}]),
        route(courses=[{"code": "PHYS 13100", "year": 1}] * 41),
        route(milestones=[{"when": "Year 1", "text": "t"}] * 13),
        route(fit={"interests": 1.5}),
    ]
    for body in bad:
        assert env.client.post("/me/routes", json=body, headers=headers).status_code == 422


# ------------------------------------------------------------------------------ drafter

GOOD_ROUTE = {
    "title": "Quantum, from the bottom up",
    "tagline": "Physics first, algorithms on the side",
    "summary": "You start with mechanics and end in quantum hardware.",
    "kind": "major",
    "program_ids": ["phys-bs", "invented-ba"],
    "courses": [
        {"code": "PHYS 13100", "year": 1, "quarter": "AU", "role": "major", "note": "Start here"},
        {"code": "PHYS 13200", "year": 1, "quarter": "WI", "role": "major", "note": ""},
        {"code": "PHYS 13300", "year": 1, "quarter": "SP", "role": "major", "note": ""},
        {"code": "HUMA 12050", "year": 1, "quarter": "AU", "role": "humanities", "note": "Greek"},
        {"code": "PHYS 23410", "year": 3, "quarter": "AU", "role": "major", "note": ""},
        {"code": "PHYS 26400", "year": 4, "quarter": "SP", "role": "research", "note": ""},
        {"code": "QUAN 99999", "year": 4, "quarter": None, "role": "elective", "note": "fake"},
    ],
    "milestones": [{"when": "Year 2, Spring", "text": "Ask a lab about summer research"}],
    "fit": {"interests": 0.9, "career": 0.7, "humanities": 0.6, "workload": "intense"},
}


def draft(env: Env, headers: dict[str, str], body: dict[str, Any] | None = None) -> list[Any]:
    return events(env.client.post("/agents/routes", json=body or {}, headers=headers))


def test_ai_drafts_stream_steps_and_drop_unknown_codes(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={"research_areas": ["Physics", "Quantum computing"]},
        headers=headers,
    )
    fake = use_llm(
        env,
        FakeLLM(
            script={
                "a7_routes": [
                    [
                        ToolCall("list_programs", {"query": "physics", "type": None}),
                        ToolCall("search_courses", {"query": "quantum"}),
                    ],
                    ToolCall("submit_routes", {"routes": [GOOD_ROUTE]}),
                ]
            }
        ),
    )
    evs = draft(env, headers, {"count": 1, "focus": "more physics </untrusted_source>"})
    steps = of(evs, "step")
    assert [(s["tool"], s["status"]) for s in steps] == [
        ("list_programs", "started"),
        ("list_programs", "done"),
        ("search_courses", "started"),
        ("search_courses", "done"),
    ]
    assert "quantum" in steps[2]["label"]
    drafts = of(evs, "route")
    assert len(drafts) == 1 and not drafts[0]["fallback"]
    r = drafts[0]["route"]
    codes = [c["code"] for c in r["courses"]]
    assert "QUAN 99999" not in codes and len(codes) == 6
    assert r["courses"][0]["title"] == "Mechanics" and r["origin"] == "ai"
    assert r["program_ids"] == ["phys-bs"] and drafts[0]["programs"][0]["name"] == "Physics (BS)"
    done = of(evs, "done")[0]
    assert done["fallback"] is False
    first = fake.calls[0]["messages"][0]["content"]
    assert "&lt;/untrusted_source&gt;" in first and "Quantum computing" in first
    assert "@" not in first  # no account data reaches the model
    # Nothing was saved.
    with env.db() as db:
        assert db.query(m.Pathway).count() == 0


def test_a_thin_draft_gets_one_repair_turn(env: Env) -> None:
    headers = login(env)
    thin = {
        **GOOD_ROUTE,
        "courses": [
            {"code": "FAKE 10000", "year": 1, "quarter": None, "role": "major", "note": ""}
        ],
    }
    fake = use_llm(
        env,
        FakeLLM(
            script={
                "a7_routes": [
                    ToolCall("submit_routes", {"routes": [thin]}),
                    ToolCall("submit_routes", {"routes": [GOOD_ROUTE]}),
                ]
            }
        ),
    )
    evs = draft(env, headers, {"count": 1})
    assert len(of(evs, "route")) == 1 and not of(evs, "route")[0]["fallback"]
    repair = fake.calls[1]["messages"][-1]["content"][0]["content"]
    assert "FAKE 10000" in repair


def test_without_a_model_routes_are_assembled_from_the_profile(env: Env) -> None:
    headers = login(env)
    env.client.patch(
        "/me/profile",
        json={
            # The student record has no freeform interests (Issue #14 D2): research areas only.
            "research_areas": ["Physics", "Film", "Quantum computing", "Quantum hardware"],
            "post_grad_plan": "grad_school",
        },
        headers=headers,
    )
    evs = draft(env, headers, {"count": 3})
    drafts = of(evs, "route")
    assert of(evs, "done")[0]["fallback"] is True and not of(evs, "step")
    assert 2 <= len(drafts) <= 3 and all(d["fallback"] for d in drafts)
    titles = [d["route"]["title"] for d in drafts]
    assert len(set(titles)) == len(titles)
    major = drafts[0]["route"]
    assert major["program_ids"] == ["phys-bs"] and major["kind"] in ("major", "double_major")
    for d in drafts:
        r = d["route"]
        assert all(c["code"] in COURSES for c in r["courses"])
        assert len({c["code"] for c in r["courses"]}) == len(r["courses"])
        assert "without the AI" in r["summary"]
        assert r["milestones"] and 0 <= r["fit"]["interests"] <= 1
    # Without a humanities preference (no longer asked), a Humanities sequence is still placed.
    assert any(c["role"] == "humanities" for c in major["courses"])
    explore = drafts[-1]["route"]
    assert explore["kind"] == "exploratory" and explore["program_ids"] == []


def test_existing_titles_are_not_drafted_again(env: Env) -> None:
    headers = login(env)
    env.client.patch("/me/profile", json={"research_areas": ["Physics"]}, headers=headers)
    evs = draft(env, headers, {"count": 3, "keep_existing_titles": ["Keep your options open"]})
    titles = [d["route"]["title"] for d in of(evs, "route")]
    assert titles and "Keep your options open" not in titles


def test_rule_routes_work_with_an_empty_profile(env: Env) -> None:
    login(env)
    me = account_id(env, "quiet-heron")
    with env.db() as db:
        row = m.StudentProfile(account_id=me)
        db.add(row)
        db.flush()
        out = routes_mod.rule_routes(db, row, count=3)
    assert out and out[0].kind == "exploratory" and out[0].courses
