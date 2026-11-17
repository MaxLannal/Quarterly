"""Saved plans, item edits and change sets (prompt 06) on the fake 2099-00 fixture."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from api.config import get_settings
from api.db import models as m
from api.repo import plans as repo
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from auth_test_support import Env, auth_env, csrf, migrated_database
from planner_core.models import AddOp, MoveOp, RemoveOp

pytestmark = pytest.mark.db

STATE: dict[str, Any] = {
    "catalog_year": "2099-00",
    "entry_term": "2099-AU",
    "programs": [{"program_id": "test-bs"}],
    "items": [
        {"course": "TEST 10000", "term": "2099-AU"},
        {"course": "TEST 10100", "term": "2100-WI"},
    ],
    "goals": [
        {"id": "g1", "type": "light_quarter", "scope": "term", "term": "2100-SP", "max_courses": 2}
    ],
    "credits": [{"kind": "AP", "label": "AP Fake", "maps_to": "TEST 20300", "units": 100}],
}


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


def login(env: Env, name: str = "quiet-heron") -> dict[str, str]:
    return csrf(env.signup(name))


def create(env: Env, headers: dict[str, str], **extra: Any) -> dict[str, Any]:
    resp = env.client.post(
        "/plans", json={"name": "Main", "state": STATE, **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


def test_plans_need_login_and_csrf(env: Env) -> None:
    assert env.client.get("/plans").status_code == 401
    headers = login(env)
    assert env.client.post("/plans", json={"name": "x", "state": STATE}).status_code == 403
    assert env.client.get("/plans", headers=headers).json() == []


def test_create_read_update_list(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    assert plan["is_primary"] is True and plan["plan_hash"].startswith("sha256:")
    state = plan["state"]
    assert [i["course"] for i in state["items"]] == ["TEST 10000", "TEST 10100"]
    assert state["goals"][0]["max_courses"] == 2 and state["credits"][0]["maps_to"] == "TEST 20300"
    assert state["programs"][0]["program_id"] == "test-bs"
    second = create(env, headers, is_primary=True)
    listed = env.client.get("/plans", headers=headers).json()
    assert [p["id"] for p in listed] == [second["id"], plan["id"]] and listed[0]["is_primary"]
    new_state = {**STATE, "goals": [], "placements": ["TEST 10000"]}
    updated = env.client.patch(
        f"/plans/{plan['id']}",
        json={"name": "Renamed", "is_primary": True, "state": new_state},
        headers=headers,
    ).json()
    assert updated["name"] == "Renamed" and updated["state"]["goals"] == []
    assert len(updated["state"]["items"]) == 2  # items change only through /items
    bad = env.client.patch(
        f"/plans/{plan['id']}",
        json={"state": {**STATE, "catalog_year": "2026-27"}},
        headers=headers,
    )
    assert bad.status_code == 422


def test_invalid_states_are_refused(env: Env) -> None:
    headers = login(env)
    for state in (
        {**STATE, "items": [{"course": "NOPE 10000", "term": "2099-AU"}]},
        {**STATE, "programs": [{"program_id": "nope"}]},
        {**STATE, "catalog_year": "1999-00"},
    ):
        resp = env.client.post("/plans", json={"name": "x", "state": state}, headers=headers)
        assert resp.status_code == 422, resp.text


def test_other_accounts_cannot_see_a_plan(env: Env) -> None:
    plan = create(env, login(env))
    other = env.browser()
    them = csrf(env.signup("loud-heron", client=other))
    assert other.get(f"/plans/{plan['id']}", headers=them).status_code == 404
    assert other.delete(f"/plans/{plan['id']}", headers=them).status_code == 404
    assert other.get(f"/plans/{uuid.uuid4()}", headers=them).status_code == 404


def test_item_edits_need_the_current_hash(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    url = f"/plans/{plan['id']}/items"
    ops = [{"op": "add", "course": "TEST 20000", "term": "2100-SP"}]
    stale = env.client.patch(
        url, json={"base_plan_hash": "sha256:old", "ops": ops}, headers=headers
    )
    assert stale.status_code == 409 and stale.json()["detail"]["plan_hash"] == plan["plan_hash"]
    ok = env.client.patch(
        url, json={"base_plan_hash": plan["plan_hash"], "ops": ops}, headers=headers
    )
    assert ok.status_code == 200 and len(ok.json()["state"]["items"]) == 3
    missing = [{"op": "remove", "course": "TEST 20400", "term": "2100-SP"}]
    bad = env.client.patch(
        url, json={"base_plan_hash": ok.json()["plan_hash"], "ops": missing}, headers=headers
    )
    assert bad.status_code == 422


def test_duplicate_delete_import_compare(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    copy = env.client.post(f"/plans/{plan['id']}/duplicate", headers=headers).json()
    assert copy["name"] == "Main (copy)" and not copy["is_primary"]
    other_state = {
        **STATE,
        "items": [
            {"course": "TEST 10000", "term": "2100-WI"},
            {"course": "TEST 20000", "term": "2100-SP"},
        ],
    }
    imported = env.client.post(
        "/plans/import", json={"plans": [{"name": "Local", "state": other_state}]}, headers=headers
    ).json()
    compare = env.client.get(
        f"/plans/compare?a={plan['id']}&b={imported[0]['id']}", headers=headers
    ).json()
    kinds = sorted(op["op"] for op in compare["ops_a_to_b"])
    assert kinds == ["add", "move", "remove"]
    assert compare["metrics"]["a"]["courses"] == 2
    assert env.client.delete(f"/plans/{copy['id']}", headers=headers).status_code == 204
    assert env.client.get(f"/plans/{copy['id']}", headers=headers).status_code == 404
    bad = {"plans": [{"name": "x", "state": {**STATE, "programs": [{"program_id": "nope"}]}}]}
    assert env.client.post("/plans/import", json=bad, headers=headers).status_code == 422


def store(env: Env, plan_id: str, ops: list[Any], base: str) -> str:
    with env.db() as db:
        row = db.get(m.Plan, uuid.UUID(plan_id))
        assert row is not None
        cs = repo.store_change_set(
            db, row, origin="generate", ops=ops, base_plan_hash=base, preview=None
        )
        db.commit()
        return str(cs.id)


def test_change_set_lifecycle(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    pid, base = plan["id"], plan["plan_hash"]
    ops = [
        MoveOp(course="TEST 10100", from_term="2100-WI", to_term="2100-SP"),
        AddOp(course="TEST 20000", term="2100-AU"),
    ]
    cs = store(env, pid, ops, base)
    listed = env.client.get(f"/plans/{pid}/changesets", headers=headers).json()
    assert [c["id"] for c in listed] == [cs] and listed[0]["status"] == "proposed"
    url = f"/plans/{pid}/changesets/{cs}"
    typed = env.client.post(
        f"{url}/apply",
        json={"base_plan_hash": base, "confirmation_text": "I agree"},
        headers=headers,
    )
    assert typed.status_code == 422
    none = env.client.post(
        f"{url}/apply", json={"base_plan_hash": base, "terms": ["2101-SP"]}, headers=headers
    )
    assert none.status_code == 422
    applied = env.client.post(
        f"{url}/apply", json={"base_plan_hash": base, "terms": ["2100-SP"]}, headers=headers
    )
    assert applied.status_code == 200, applied.text
    terms = {i["course"]: i["term"] for i in applied.json()["state"]["items"]}
    assert terms == {"TEST 10000": "2099-AU", "TEST 10100": "2100-SP"}  # only the selected quarter
    again = env.client.post(
        f"{url}/apply", json={"base_plan_hash": applied.json()["plan_hash"]}, headers=headers
    )
    assert again.status_code == 409
    assert env.client.post(f"{url}/discard", headers=headers).status_code == 409

    # A change set made before the plan changed goes stale and is re-previewed.
    old = store(env, pid, [RemoveOp(course="TEST 10000", term="2099-AU")], base)
    stale = env.client.post(
        f"/plans/{pid}/changesets/{old}/apply",
        json={"base_plan_hash": applied.json()["plan_hash"]},
        headers=headers,
    )
    assert stale.status_code == 409
    row = next(
        c
        for c in env.client.get(f"/plans/{pid}/changesets", headers=headers).json()
        if c["id"] == old
    )
    assert row["status"] == "stale" and row["preview_report"] is not None
    discarded = env.client.post(f"/plans/{pid}/changesets/{old}/discard", headers=headers).json()
    assert discarded["status"] == "discarded"
    assert (
        env.client.post(
            f"/plans/{pid}/changesets/{uuid.uuid4()}/discard", headers=headers
        ).status_code
        == 404
    )


def test_generate_explains_a_missing_core(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    resp = env.client.post(f"/plans/{plan['id']}/generate", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["variants"] == [] and "Core" in body["infeasible"]["message"]
    local = env.client.post(
        "/plans/generate",
        json={"plan": {**STATE, "programs": [{"program_id": "nope"}]}},
        headers=headers,
    )
    assert local.status_code == 422


def test_saving_the_whole_plan_keeps_item_ids(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    items = plan["state"]["items"]
    first_id = items[0]["id"]
    moved = [{**items[0], "term": "2100-SP"}, items[1], {"course": "TEST 20000", "term": "2101-WI"}]
    saved = env.client.patch(
        f"/plans/{plan['id']}", json={"state": {**plan["state"], "items": moved}}, headers=headers
    ).json()
    by_course = {i["course"]: i for i in saved["state"]["items"]}
    assert (
        by_course["TEST 10000"]["id"] == first_id and by_course["TEST 10000"]["term"] == "2100-SP"
    )
    assert "TEST 20000" in by_course
    # An id-targeted change set made now still applies after another save.
    cs = store(env, plan["id"], [RemoveOp(item_id=first_id)], saved["plan_hash"])
    applied = env.client.post(
        f"/plans/{plan['id']}/changesets/{cs}/apply",
        json={"base_plan_hash": saved["plan_hash"]},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert "TEST 10000" not in {i["course"] for i in applied.json()["state"]["items"]}


def test_old_client_hash_does_not_spoil_a_fresh_change_set(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    cs = store(env, plan["id"], [AddOp(course="TEST 20000", term="2100-AU")], plan["plan_hash"])
    resp = env.client.post(
        f"/plans/{plan['id']}/changesets/{cs}/apply",
        json={"base_plan_hash": "sha256:old"},
        headers=headers,
    )
    assert resp.status_code == 409
    row = env.client.get(f"/plans/{plan['id']}/changesets", headers=headers).json()[0]
    assert row["status"] == "proposed"
