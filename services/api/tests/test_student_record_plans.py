"""Credits and taken courses belong to the student record, not to one plan (Issue #14 steps
10-15): every saved plan reads them from the record, saving a plan writes them back, and a new
plan never overwrites a record that already has some."""

# The fixtures `db_url` and `env` come from test_plans_api (the fake 2099-00 catalog).
# ruff: noqa: F811

from __future__ import annotations

from typing import Any

import pytest
from auth_test_support import Env
from test_plans_api import STATE, create, db_url, env, login  # noqa: F401

pytestmark = pytest.mark.db

TAKEN = {"course": "TEST 10000", "term": "2099-AU", "status": "completed", "grade": "B+"}


def with_taken(**extra: Any) -> dict[str, Any]:
    return {**STATE, "items": [TAKEN, STATE["items"][1]], **extra}


def profile(env: Env) -> dict[str, Any]:
    body: dict[str, Any] = env.client.get("/me/profile").json()
    return body


def test_a_new_plan_fills_an_empty_record(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers, state=with_taken())
    taken = [i for i in plan["state"]["items"] if i["status"] == "completed"]
    assert len(taken) == 1 and taken[0]["id"].startswith("t") and taken[0]["grade"] == "B+"
    record = profile(env)
    assert [c["course"] for c in record["taken_courses"]] == ["TEST 10000"]
    assert record["credits"][0]["maps_to"] == "TEST 20300"


def test_every_plan_shows_the_record_and_a_new_plan_does_not_overwrite_it(env: Env) -> None:
    headers = login(env)
    first = create(env, headers, state=with_taken())
    # A second plan (an import from this browser) brings other credits and no taken courses:
    # the record wins.
    second = create(
        env,
        headers,
        state={**STATE, "credits": [{"kind": "placement", "label": "Placement", "units": 0}]},
    )
    assert [c["kind"] for c in second["state"]["credits"]] == ["AP"]
    assert any(i["course"] == "TEST 10000" for i in second["state"]["items"])
    assert profile(env)["credits"][0]["kind"] == "AP"
    again = env.client.get(f"/plans/{first['id']}", headers=headers).json()
    assert again["state"]["credits"] == second["state"]["credits"]


def test_saving_a_plan_writes_the_record_and_other_plans_see_it(env: Env) -> None:
    headers = login(env)
    first = create(env, headers, state=with_taken())
    second = create(env, headers)
    new_credits = [{"kind": "transfer", "label": "Transfer course", "units": 100}]
    saved = env.client.patch(
        f"/plans/{second['id']}",
        json={"state": {**second["state"], "credits": new_credits}},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert profile(env)["credits"][0]["kind"] == "transfer"
    shown = env.client.get(f"/plans/{first['id']}", headers=headers).json()
    assert shown["state"]["credits"][0]["kind"] == "transfer"


def test_marking_a_course_done_moves_it_to_the_record(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers)
    items = plan["state"]["items"]
    done = [{**items[0], "status": "completed"}, items[1]]
    saved = env.client.patch(
        f"/plans/{plan['id']}", json={"state": {**plan["state"], "items": done}}, headers=headers
    ).json()
    taken = [i for i in saved["state"]["items"] if i["status"] == "completed"]
    assert [i["course"] for i in taken] == ["TEST 10000"] and taken[0]["id"].startswith("t")
    assert len(saved["state"]["items"]) == 2
    assert [c["course"] for c in profile(env)["taken_courses"]] == ["TEST 10000"]
    # Saving again keeps the taken course's id (change sets refer to it).
    again = env.client.patch(
        f"/plans/{plan['id']}", json={"state": saved["state"]}, headers=headers
    ).json()
    assert [i["id"] for i in again["state"]["items"]] == [i["id"] for i in saved["state"]["items"]]


def test_the_dashboard_edits_what_plans_show(env: Env) -> None:
    headers = login(env)
    plan = create(env, headers, state=with_taken())
    resp = env.client.patch("/me/profile", json={"taken_courses": []}, headers=headers)
    # The record's courses are looked up in the current campus catalog, which the 2099
    # fixture does not have; an empty list needs no lookup.
    assert resp.status_code == 200, resp.text
    shown = env.client.get(f"/plans/{plan['id']}", headers=headers).json()
    assert not any(i["status"] == "completed" for i in shown["state"]["items"])


def test_saving_a_plan_keeps_taken_courses_before_its_first_quarter(env: Env) -> None:
    headers = login(env)
    early = {**TAKEN, "term": "2099-AU"}
    plan = create(env, headers, state=with_taken(items=[early, STATE["items"][1]]))
    # A plan that starts a year later cannot show the 2099-AU course; saving it keeps the course.
    later = {**plan["state"], "entry_term": "2100-AU"}
    later["items"] = [i for i in later["items"] if i["status"] != "completed"]
    later["items"] = [{**i, "term": "2101-WI"} for i in later["items"]]
    saved = env.client.patch(f"/plans/{plan['id']}", json={"state": later}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert [c["term"] for c in profile(env)["taken_courses"]] == ["2099-AU"]


def test_the_account_export_has_the_record_of_a_student_who_only_saved_a_plan(env: Env) -> None:
    headers = login(env)
    create(env, headers, state=with_taken())
    body = env.client.get("/account/export").json()
    profile = body["profile"]["profile"]  # {"profile": the record, "routes": [...]}
    assert profile is not None and profile["credits"][0]["maps_to"] == "TEST 20300"
    assert profile["taken_courses"][0]["course"] == "TEST 10000"
    assert "## General Information" in profile["student_md"]
