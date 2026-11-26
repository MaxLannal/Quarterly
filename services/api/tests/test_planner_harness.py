"""The planner agent's generate mode (issue #17) on the real 2026-27 seed, with FakeLLM only.

The fake model's plans are built from the solver's own placements, so a "good" fill passes
the verifier; the tests then break it on purpose to drive the repair step."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from api.agents.planner.harness import PlannerRun
from api.agents.runtime import RunLog
from api.config import get_settings
from api.db import models as m
from api.repo import catalog as catalog_repo
from api.repo.rules import load_verify_inputs
from api.schemas.planner import PlannerRequest
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from auth_test_support import Env, auth_env, migrated_database
from llm_gateway.api import FakeLLM, ToolCall
from planner_core.generator import generate, horizon
from planner_core.models import GenerateOptions, PlanState
from pydantic import BaseModel

pytestmark = pytest.mark.db

SEED = Path(__file__).resolve().parents[3] / "data" / "seed" / "2026-27"
TASK = "a1_planner_agent"
STATE: dict[str, Any] = {
    "catalog_year": "2026-27",
    "entry_term": "2026-AU",
    "placements": ["MATH 15100"],
    "programs": [{"program_id": "core"}, {"program_id": "cmsc-bs"}],
}
INTERESTS = {"interests": {"option": None, "text": "machine learning, philosophy of mind"}}


@pytest.fixture(scope="module")
def env() -> Iterator[Env]:
    with migrated_database() as url, pytest.MonkeyPatch.context() as mp:
        mp.setattr(get_settings(), "show_unpublished_programs", True)
        with auth_env(url, mp) as e:
            with e.db() as db:
                upsert_bundle(db, load_bundle(SEED))
            yield e


@pytest.fixture(scope="module")
def solved(env: Env) -> list[tuple[str, str]]:
    """(course, term) of one verified CS BS plan, from the solver."""
    state = PlanState.model_validate(STATE)
    with env.db() as db:
        rules, catalog = load_verify_inputs(
            db, state, show_unpublished=True, whole_catalog=True, section_terms=horizon(state)
        )
    result = generate(state, rules, catalog, GenerateOptions(variants=1, time_limit_s=20))
    assert result.variants, result.infeasible
    return [(i.course, i.term) for i in result.variants[0].plan.items if i.course]


def groups_of(placed: list[tuple[str, str]]) -> list[dict[str, Any]]:
    by_subject: dict[str, list[tuple[str, str]]] = {}
    for code, term in placed:
        by_subject.setdefault(code.split()[0], []).append((code, term))
    return [
        {
            "id": f"g{n}",
            "title": f"{subject} courses",
            "kind": "major" if subject == "CMSC" else "core",
            "courses": [{"code": c, "term": t} for c, t in rows],
            "why": "You said you like machine learning, so these come early.",
            "rules": ["G38"],
        }
        for n, (subject, rows) in enumerate(sorted(by_subject.items()), 1)
    ]


def fill(placed: list[tuple[str, str]]) -> ToolCall:
    return ToolCall("submit_plan", {"groups": groups_of(placed), "notes": ""})


def no_questions() -> ToolCall:
    return ToolCall("submit_questions", {"questions": []})


def explain(placed: list[tuple[str, str]]) -> ToolCall:
    return ToolCall(
        "submit_explanations",
        {
            "groups": [
                {
                    "id": g["id"],
                    "why": "Machine learning needs this base.",
                    "citations": ["profile:interests"],
                }
                for g in groups_of(placed)
            ]
        },
    )


def run(env: Env, fake: FakeLLM, **req: Any) -> list[dict[str, Any]]:
    account_id = req.pop("_account", None)
    body = PlannerRequest.model_validate({"mode": "generate", "plan": STATE, **req})
    with env.db() as db:
        account = db.get(m.Account, account_id) if account_id else None
        planner = PlannerRun.build(
            db,
            fake,
            body,
            account=account,
            saved=None,
            show_unpublished=True,
            statuses=catalog_repo.ALL_STATUSES,
            log=RunLog(),
        )
        out = [
            e.model_dump(mode="json") if isinstance(e, BaseModel) else e
            for e in planner.generate_events()
        ]
    return out


def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


def answers(text: str = "machine learning, philosophy of mind") -> dict[str, Any]:
    return {"interests": {"option": None, "text": text}}


def test_generate_cs_student_valid_plan(env: Env, solved: list[tuple[str, str]]) -> None:
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    types = [e["type"] for e in events]
    assert types[0] == "step" and types[-1] == "done"
    plan = of(events, "plan")
    assert len(plan) == 1 and plan[0]["verdict"] == "valid"
    proposals = of(events, "proposal")
    assert len(proposals) == len(groups_of(solved))
    assert all(p["why"] for p in proposals)
    assert any(c["id"] == "interests" for p in proposals for c in p["citations"])
    assert {r["id"] for p in proposals for r in p["rules"]} == {"G38"}
    added = sorted(
        (o["course"], o["term"]) for p in proposals for o in p["ops"] if o["op"] == "add"
    )
    assert added == sorted(solved)
    # The student's interests reached the model, inside student.md.
    assert "Interests: Machine learning; Philosophy of mind" in str(fake.calls[0]["messages"])


def test_generate_asks_interests_when_empty(env: Env) -> None:
    fake = FakeLLM()
    events = run(env, fake)
    question = of(events, "question")
    assert len(question) == 1 and question[0]["field"] == "interests"
    assert question[0]["text"] == "Which subjects or topics interest you most?"
    assert fake.calls == []  # a question from the question file needs no model
    with env.db() as db:
        row = db.get(m.AgentRun, uuid.UUID(question[0]["run_id"]))
        assert row is not None and row.state is not None and row.state["phase"] == "ask"


def test_resume_with_answer_continues(env: Env, solved: list[tuple[str, str]]) -> None:
    first = run(env, FakeLLM())
    run_id = of(first, "question")[0]["run_id"]
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(
        env,
        fake,
        run_id=run_id,
        answer={"question_id": "interests", "text": "robotics and machine learning"},
    )
    assert not of(events, "question") and of(events, "plan")[0]["verdict"] == "valid"
    done = of(events, "done")[0]
    assert done["profile_answers"] == {"interests": ["Robotics", "Machine learning"]}
    with env.db() as db:
        assert db.get(m.AgentRun, uuid.UUID(run_id)).state is None  # cleared when the run ends


def test_resume_stores_a_profile_proposal_for_an_account(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    with env.db() as db:
        acct = m.Account(
            username="plan-owl", email="owl@example.edu", email_verified_day=dt.date.today()
        )
        db.add(acct)
        db.commit()
        account_id = acct.id
    first = run(env, FakeLLM(), _account=account_id)
    run_id = of(first, "question")[0]["run_id"]
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    run(
        env,
        fake,
        _account=account_id,
        run_id=run_id,
        answer={"question_id": "interests", "text": "robotics"},
    )
    with env.db() as db:
        rows = db.scalars(
            sa.select(m.ProfileProposal).where(m.ProfileProposal.account_id == account_id)
        ).all()
        assert [(r.field, r.value, r.status) for r in rows] == [
            ("interests", ["Robotics"], "proposed")
        ]


def test_resume_after_state_expired(env: Env) -> None:
    first = run(env, FakeLLM())
    run_id = of(first, "question")[0]["run_id"]
    with env.db() as db:
        row = db.get(m.AgentRun, uuid.UUID(run_id))
        assert row is not None and row.state is not None
        row.state = {**row.state, "day": (dt.date.today() - dt.timedelta(days=3)).isoformat()}
        db.commit()
    events = run(env, FakeLLM(), run_id=run_id, answer={"question_id": "interests", "text": "x"})
    assert [e["type"] for e in events] == ["error"] and events[0]["reason"] == "expired"


def test_fill_rejects_unknown_code_then_accepts_repair(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    bad = fill([*solved, ("CMSC 99999", solved[0][1])])
    fake = FakeLLM(script={TASK: [no_questions(), bad, fill(solved), explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    assert of(events, "plan")[0]["verdict"] == "valid"
    # The second fill call carries the check's message (the one repair turn of the loop).
    assert "CMSC 99999 is not a course in the catalog" in str(fake.calls[2]["messages"])


def test_fill_that_fails_twice_ends_with_an_error(env: Env, solved: list[tuple[str, str]]) -> None:
    bad = fill([*solved, ("CMSC 99999", solved[0][1])])
    fake = FakeLLM(script={TASK: [no_questions(), bad, bad]})
    events = run(env, fake, profile_answers=answers())
    assert of(events, "error") and not of(events, "proposal") and not of(events, "plan")


def swapped(solved: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], str, str]:
    t1 = dict(solved)["CMSC 14100"]
    t2 = dict(solved)["CMSC 14200"]
    out = [(c, t2 if c == "CMSC 14100" else t1 if c == "CMSC 14200" else t) for c, t in solved]
    return out, t1, t2


def test_repair_round_fixes_prereq_error(env: Env, solved: list[tuple[str, str]]) -> None:
    broken, t1, t2 = swapped(solved)
    repair = ToolCall(
        "submit_repair",
        {
            "summary": "Put the intro sequence back in order.",
            "ops": [
                {
                    "op": "move",
                    "course": "CMSC 14100",
                    "term": "",
                    "from_term": t2,
                    "to_term": t1,
                    "why": "",
                    "group_id": "",
                },
                {
                    "op": "move",
                    "course": "CMSC 14200",
                    "term": "",
                    "from_term": t1,
                    "to_term": t2,
                    "why": "",
                    "group_id": "",
                },
            ],
            "bent": [],
        },
    )
    fake = FakeLLM(script={TASK: [no_questions(), fill(broken), repair, explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    steps = [e["name"] for e in of(events, "step") if e["status"] == "started"]
    assert "Fixing the plan (round 1)" in steps
    assert of(events, "plan")[0]["verdict"] == "valid"


def test_repair_stops_on_thrash(env: Env, solved: list[tuple[str, str]]) -> None:
    broken, _, _ = swapped(solved)
    idle = ToolCall("submit_repair", {"summary": "No change.", "ops": [], "bent": []})
    fake = FakeLLM(script={TASK: [no_questions(), fill(broken), idle, idle, idle, explain(broken)]})
    events = run(env, fake, profile_answers=answers())
    plan = of(events, "plan")[0]
    assert plan["verdict"] == "invalid" and any(i["code"] == "V03" for i in plan["issues"])
    assert of(events, "proposal")  # the plan still goes to the student, never as valid
    rounds = [
        e for e in of(events, "step") if e["name"].startswith("Fixing") and e["status"] == "started"
    ]
    assert len(rounds) == 3


def test_standard_issues_go_to_repair(env: Env, solved: list[tuple[str, str]]) -> None:
    code, term = next((c, t) for c, t in solved if c.startswith("CMSC 2"))
    away = {**answers(), "terms_away": [{"term": term, "kind": "abroad"}]}
    idle = ToolCall("submit_repair", {"summary": "x", "ops": [], "bent": []})
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), idle, idle, idle, explain(solved)]})
    events = run(env, fake, profile_answers=away)
    plan = of(events, "plan")[0]
    assert plan["verdict"] == "invalid" and any(
        i["code"] == "S01" and code in i["course_ids"] for i in plan["issues"]
    )
    assert "S01" in str(fake.calls[2]["messages"])


def test_regenerate_proposes_removals_and_keeps_completed(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    placed = {c for c, _ in solved}
    dropped = next(
        c for c in ("MUSI 10100", "TAPS 10100", "ARTV 10200", "CRWR 10200") if c not in placed
    )
    done = next(c for c in ("SPAN 10100", "GRMN 10100", "ITAL 10100") if c not in placed)
    extra = [
        {"course": dropped, "term": "2026-AU"},
        {"course": done, "term": "2026-AU", "status": "completed"},
    ]
    idle = ToolCall("submit_repair", {"summary": "x", "ops": [], "bent": []})
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), idle, idle, idle, explain(solved)]})
    events = run(env, fake, profile_answers=answers(), plan={**STATE, "items": extra})
    replace = [p for p in of(events, "proposal") if p["kind"] == "replace"]
    assert len(replace) == 1 and replace[0]["title"] == "Courses this plan replaces"
    assert [(o["op"], o.get("course")) for o in replace[0]["ops"]] == [("remove", dropped)]
    assert replace == of(events, "proposal")[-1:]  # the removals come last
    touched = {o.get("course") for p in of(events, "proposal") for o in p["ops"]}
    assert done not in touched


def test_plan_without_a_major_asks_to_add_one(env: Env) -> None:
    events = run(
        env,
        FakeLLM(),
        profile_answers=answers(),
        plan={**STATE, "programs": [{"program_id": "core"}]},
    )
    assert [e["type"] for e in events][-2:] == ["message", "done"]
    assert "+ Program" in of(events, "message")[0]["text"]


def test_fill_submits_without_tools_after_the_lookups_run_out(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    """Live finding (2026-11-26): Opus 5.5 looked up more courses than the step allowed and the
    run ended (budget_tool_calls). The harness now asks once more, with no tools."""
    from api.agents.planner.guideline import load_planner_config

    lookups = [
        ToolCall("get_course", {"code": "CMSC 14100"}),
        ToolCall("get_course", {"code": "CMSC 14200"}),
    ]
    fake = FakeLLM(script={TASK: [no_questions(), lookups, fill(solved), explain(solved)]})
    body = PlannerRequest.model_validate(
        {"mode": "generate", "plan": STATE, "profile_answers": answers()}
    )
    config = load_planner_config().model_copy(update={"tool_calls_per_step": 1})
    with env.db() as db:
        planner = PlannerRun.build(
            db, fake, body, account=None, saved=None, show_unpublished=True,
            statuses=catalog_repo.ALL_STATUSES, log=RunLog(), config=config,
        )  # fmt: skip
        events = [e.model_dump(mode="json") for e in planner.generate_events()]
    assert of(events, "plan")[0]["verdict"] == "valid"
    retry = fake.calls[-2]
    assert retry["tools"] == ["submit_plan"] and "used all your catalog lookups" in str(
        retry["messages"]
    )


def test_an_impossible_request_is_explained_before_the_plan(
    env: Env, solved: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC journey B: when the solver proves that no plan fits, the student hears why, in the
    rules that conflict, and still gets the closest plan to work from."""
    from types import SimpleNamespace

    import api.agents.planner.harness as harness
    from planner_core.models import Conflict, Infeasibility

    proof = Infeasibility(
        message="Graduating by Spring 2030 needs 5 more courses than your quarters allow.",
        conflicts=[Conflict(id="units", kind="load", label="Keeping every quarter full time")],
    )
    monkeypatch.setattr(
        harness, "generate", lambda *a, **k: SimpleNamespace(variants=[], infeasible=proof)
    )
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    notice = of(events, "message")[0]["text"]
    assert notice.startswith("No plan fits all of these rules.")
    assert proof.message in notice and "Keeping every quarter full time" in notice
    assert [e["type"] for e in events].index("message") < [e["type"] for e in events].index("plan")
    assert proof.message in str(fake.calls[1]["messages"])  # the model hears it too
