"""The dashboard profile (`GET/PATCH /me/profile`) and its export helper: login required, the
row created lazily, the email read from the account and never stored in the profile, validation,
and true partial updates."""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from api.db import models as m
from api.profile_data import export_profile
from auth_test_support import Env
from test_profile_support import account_id, db_url_fixture, env_fixture, login  # noqa: F401

pytestmark = pytest.mark.db


def patch(env: Env, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return env.client.patch("/me/profile", json=body, headers=headers)


def test_everything_needs_login(env: Env) -> None:
    assert env.client.get("/me/profile").status_code == 401
    assert env.client.patch("/me/profile", json={"interests": ["x"]}).status_code == 401
    assert env.client.post("/agents/interview", json={"mode": "start"}).status_code == 401


def test_the_routes_are_gone(env: Env) -> None:
    # Issue #15 removed "Your routes": the planner makes every plan proposal.
    headers = login(env)
    assert env.client.get("/me/routes", headers=headers).status_code == 404
    assert env.client.post("/agents/routes", json={}, headers=headers).status_code == 404


def test_the_row_is_created_lazily_and_the_email_comes_from_the_account(env: Env) -> None:
    login(env, "quiet-heron", email="heron.q@uchicago.edu")
    me = account_id(env, "quiet-heron")
    with env.db() as db:
        assert db.get(m.StudentProfile, me) is None
    resp = env.client.get("/me/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == "quiet-heron"
    assert body["email"] == "heron.q@uchicago.edu"
    assert body["member_since"] and body["completeness"] == 0
    assert resp.headers["cache-control"] == "no-store"
    with env.db() as db:
        row = db.get(m.StudentProfile, me)
        assert row is not None
        # Decision 5: the email lives only in account.email.
        values = [getattr(row, c.key) for c in sa.inspect(m.StudentProfile).mapper.column_attrs]
        assert "heron.q@uchicago.edu" not in repr(values)
        assert "@" not in repr(values)


def test_patch_cleans_lists_and_scrubs_text(env: Env) -> None:
    headers = login(env)
    resp = patch(
        env,
        headers,
        {
            "class_year": 2029,
            "interests": ["  Physics ", "physics", "Film  studies", ""],
            "humanities_goal": "enjoy",
            "humanities_topics": ["Greek tragedy"],
            "career_plans": "Quantum research. Write to me at jo@uchicago.edu or 773-702-1234.",
            "workload": "balanced",
            "intended_programs": ["phys-bs"],
            "interview": {
                "covered": ["class_year", "interests", "class_year"],
                "turns": [{"role": "student", "text": f"turn {i}"} for i in range(30)],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interests"] == ["Physics", "Film studies"]
    assert (
        body["career_plans"]
        == "Quantum research. Write to me at [email removed] or [phone removed]."
    )
    assert body["programs"] == [{"id": "phys-bs", "name": "Physics (BS)"}]
    assert body["interview"]["covered"] == ["class_year", "interests"]
    turns = body["interview"]["turns"]
    assert len(turns) == 24 and turns[-1]["text"] == "turn 29"
    assert body["completeness"] == pytest.approx(round(5 / 7, 3))


@pytest.mark.parametrize(
    "bad",
    [
        {"class_year": 2019},
        {"class_year": 2041},
        {"humanities_goal": "skim"},
        {"workload": "extreme"},
        {"interests": [f"item {i}" for i in range(25)]},
        {"interests": ["x" * 61]},
        {"career_plans": "y" * 1201},
        {"intended_programs": ["nope-ba"]},
        {"interview": {"turns": [{"role": "guide", "text": "z" * 2001}]}},
    ],
)
def test_patch_validation(env: Env, bad: dict[str, Any]) -> None:
    headers = login(env)
    assert patch(env, headers, bad).status_code == 422


def test_patch_is_partial_and_null_clears(env: Env) -> None:
    headers = login(env)
    patch(env, headers, {"interests": ["Physics"], "class_year": 2028, "workload": "light"})
    body = patch(env, headers, {"research_areas": ["Quantum materials"]}).json()
    assert body["interests"] == ["Physics"] and body["class_year"] == 2028
    assert body["workload"] == "light" and body["research_areas"] == ["Quantum materials"]
    body = patch(env, headers, {"class_year": None, "interests": None}).json()
    assert body["class_year"] is None and body["interests"] == []
    assert body["research_areas"] == ["Quantum materials"] and body["workload"] == "light"
    body = patch(
        env, headers, {"portrait": {"headline": "A physicist", "themes": ["a", "A"]}}
    ).json()
    assert body["portrait"] == {"headline": "A physicist", "summary": "", "themes": ["a"]}
    body = patch(
        env, headers, {"follows": {"threads": [3, 3, 4], "courses": ["PHYS 13100"]}}
    ).json()
    assert body["follows"] == {"threads": [3, 4], "courses": ["PHYS 13100"]}
    assert body["portrait"]["headline"] == "A physicist"


def test_csrf_is_required_for_writes(env: Env) -> None:
    login(env)
    assert env.client.patch("/me/profile", json={"interests": ["x"]}).status_code == 403


def test_export_profile_has_the_profile_without_the_email(env: Env) -> None:
    headers = login(env, "quiet-heron", email="heron.q@uchicago.edu")
    me = account_id(env, "quiet-heron")
    with env.db() as db:
        assert export_profile(db, me) == {"profile": None}
    patch(env, headers, {"interests": ["Physics"], "class_year": 2029})
    with env.db() as db:
        out = export_profile(db, me)
    assert out["profile"]["interests"] == ["Physics"] and out["profile"]["class_year"] == 2029
    assert set(out) == {"profile"}  # the routes went in issue #15
    assert "heron.q" not in repr(out)
