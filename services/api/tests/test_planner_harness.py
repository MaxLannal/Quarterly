"""The planner agent's generate mode (issue #17) on the real 2026-27 seed, with FakeLLM only.

The fake model's plans are built from the solver's own placements, so a "good" fill passes
the verifier; the tests then break it on purpose to drive the repair step."""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from api.agents.planner.harness import NOT_YET, PLACEMENT_ID, PlannerRun
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
from planner_core.hashing import plan_hash
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


def test_a_resumed_run_adds_up_its_tokens_and_steps(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    # Live (2026-11-26): each request overwrote the run's totals, so a run that paused for a
    # model question showed 0 tokens and only its last request's steps.
    question = ToolCall(
        "submit_questions",
        {"questions": [{"id": "Q1", "question": "Three or four courses?", "options": ["3", "4"]}]},
    )
    first = run(env, FakeLLM(script={TASK: [question]}), profile_answers=answers())
    run_id = of(first, "question")[0]["run_id"]
    fake = FakeLLM(script={TASK: [fill(solved), explain(solved)]})
    run(
        env,
        fake,
        profile_answers=answers(),
        run_id=run_id,
        answer={"question_id": "Q1", "option": "4"},
    )
    with env.db() as db:
        row = db.get(m.AgentRun, uuid.UUID(run_id))
        assert row is not None
        assert row.tokens == 3 * 120  # one call, then two; the fake reports 100 in + 20 out
        names = [s["name"] for s in row.steps if s["status"] == "started"]
        assert names.count("Reading your information") == 2  # both requests are kept


NO_PLACEMENT: dict[str, Any] = {**STATE, "placements": []}


def placement_question(env: Env) -> dict[str, Any]:
    fake = FakeLLM()
    events = run(env, fake, plan=NO_PLACEMENT, profile_answers=answers())
    questions = of(events, "question")
    assert fake.calls == []  # asked before any model call
    assert [q["question_id"] for q in questions] == [PLACEMENT_ID]
    return questions[0]


def test_a_plan_without_a_math_placement_asks_for_it_first(env: Env) -> None:
    # Live (2026-11-26): with no placement, calculus and then the CS BS could not be planned;
    # the writing step spent its time on an impossible plan and failed.
    q = placement_question(env)
    codes = [o.split(" ")[0] + " " + o.split(" ")[1] for o in q["options"][:-1]]
    assert "MATH 15100" in codes and codes == sorted(codes)
    assert all(c.startswith("MATH ") for c in codes)
    assert q["options"][-1] == NOT_YET


def test_a_placement_credit_needs_no_question(env: Env, solved: list[tuple[str, str]]) -> None:
    credit = {"kind": "placement", "label": "MATH 15100", "maps_to": None, "units": 0}
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(env, fake, plan={**NO_PLACEMENT, "credits": [credit]}, profile_answers=answers())
    assert not of(events, "question") and of(events, "plan")[0]["verdict"] == "valid"


def test_a_math_course_already_credited_needs_no_placement_question(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    # Journey B: a transfer's calculus credit counts as MATH 15100, which opens MATH 15200;
    # a placement is only the other way in, so there is nothing to ask.
    credit = {"kind": "transfer", "label": "Calculus I", "maps_to": "MATH 15100", "units": 100}
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(env, fake, plan={**NO_PLACEMENT, "credits": [credit]}, profile_answers=answers())
    assert PLACEMENT_ID not in [q["question_id"] for q in of(events, "question")]


def test_the_placement_answer_reaches_the_run_and_the_page(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    q = placement_question(env)
    option = next(o for o in q["options"] if o.startswith("MATH 15100"))
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(
        env,
        fake,
        plan=NO_PLACEMENT,
        profile_answers=answers(),
        run_id=q["run_id"],
        answer={"question_id": PLACEMENT_ID, "option": option},
    )
    assert of(events, "plan")[0]["verdict"] == "valid"  # the run planned with the placement
    assert "MATH 15100" in str(fake.calls[0]["messages"])  # and the model was told
    assert of(events, "done")[-1]["placements"] == ["MATH 15100"]  # the page adds it
    # The page's plan with the credit added is the plan the proposals were made for.
    credit = {"kind": "placement", "label": "MATH 15100", "maps_to": None, "units": 0}
    page = plan_hash(PlanState.model_validate({**NO_PLACEMENT, "credits": [credit]}))
    assert {p["base_plan_hash"] for p in of(events, "proposal")} == {page}


def test_no_placement_yet_plans_from_the_lowest_one_and_says_so(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    q = placement_question(env)
    lowest = " ".join(q["options"][0].split(" ")[:2])
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    events = run(
        env,
        fake,
        plan=NO_PLACEMENT,
        profile_answers=answers(),
        run_id=q["run_id"],
        answer={"question_id": PLACEMENT_ID, "option": NOT_YET},
    )
    assert of(events, "done")[-1]["placements"] == [lowest]
    notes = [m["text"] for m in of(events, "message")]
    assert any("not taken the math placement" in t and lowest in t for t in notes)


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


def test_a_fill_rejected_twice_keeps_the_plan_without_the_rejected_courses(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    # Live (2026-11-27): the check rejected the plan twice and the whole run was thrown away.
    # The rejected courses go; the verifier and the repair rounds see what is still missing.
    bad = fill([*solved, ("CMSC 99999", solved[0][1])])
    fake = FakeLLM(script={TASK: [no_questions(), bad, bad, explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    assert not of(events, "error") and of(events, "plan")[0]["verdict"] == "valid"
    proposed = {op["course"] for p in of(events, "proposal") for op in p["ops"]}
    assert "CMSC 99999" not in proposed and {c for c, _ in solved} <= proposed


def test_the_writing_step_has_its_own_time_limit(env: Env, solved: list[tuple[str, str]]) -> None:
    # Live (2026-11-26/27): one writing step took 297 s of the 300 s each step gets, and one
    # ran out of time (`budget_seconds`). Writing the whole plan gets `write_seconds`.
    fake = FakeLLM(script={TASK: [no_questions(), fill(solved), explain(solved)]})
    with env.db() as db:
        body = PlannerRequest.model_validate(
            {"mode": "generate", "plan": STATE, "profile_answers": answers()}
        )
        planner = PlannerRun.build(
            db, fake, body, account=None, saved=None, show_unpublished=True,
            statuses=catalog_repo.ALL_STATUSES, log=RunLog(),
        )  # fmt: skip
        specs: list[Any] = []
        real = planner.spec

        def spy(*args: Any, **kwargs: Any) -> Any:
            spec = real(*args, **kwargs)
            specs.append(spec)
            return spec

        planner.spec = spy  # type: ignore[method-assign]
        list(planner.generate_events())
    write = [s for s in specs if s.submit.name == "submit_plan"]
    others = [s for s in specs if s.submit.name != "submit_plan"]
    assert write and all(s.budget.seconds == planner.config.write_seconds for s in write)
    assert all(s.budget.seconds == planner.config.run_seconds for s in others)
    assert planner.config.write_seconds > planner.config.run_seconds


def test_a_fill_without_a_plan_twice_ends_with_an_error(env: Env) -> None:
    fake = FakeLLM(script={TASK: [no_questions(), "I cannot plan this.", "Still no."]})
    events = run(env, fake, profile_answers=answers())
    assert of(events, "error") and not of(events, "proposal") and not of(events, "plan")


def test_a_failed_step_logs_its_reason_as_a_warning(
    env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    # Live (2026-11-26): the fill failed and the reason was logged at INFO, which the API drops.
    fake = FakeLLM(script={TASK: [no_questions(), "I cannot plan this.", "Still no."]})
    with caplog.at_level(logging.WARNING, logger="api.agents"):
        run(env, fake, profile_answers=answers())
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    # The reason and the loop's detail (field names, codes and quarters, no student data).
    assert any(
        w.startswith(f"{TASK}: fill failed (invalid_output)") and "no submit_plan call" in w
        for w in warnings
    ), warnings


def test_a_kept_fill_logs_what_it_dropped(
    env: Env, solved: list[tuple[str, str]], caplog: pytest.LogCaptureFixture
) -> None:
    bad = fill([*solved, ("CMSC 99999", solved[0][1])])
    fake = FakeLLM(script={TASK: [no_questions(), bad, bad, explain(solved)]})
    with caplog.at_level(logging.WARNING, logger="api.agents"):
        run(env, fake, profile_answers=answers())
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("CMSC 99999 is not a course in the catalog" in w for w in warnings), warnings


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


def test_a_bad_repair_gets_its_repair_turn_instead_of_crashing(
    env: Env, solved: list[tuple[str, str]]
) -> None:
    """Final review 2: a repair op with no quarter or an unknown code is checked like a fill."""
    broken, t1, t2 = swapped(solved)
    bad = ToolCall(
        "submit_repair",
        {
            "summary": "x",
            "ops": [
                {
                    "op": "add",
                    "course": "CMSC 99999",
                    "term": "",
                    "from_term": "",
                    "to_term": "",
                    "why": "",
                    "group_id": "",
                }
            ],
            "bent": [],
        },
    )
    good = ToolCall(
        "submit_repair",
        {
            "summary": "Back in order.",
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
    fake = FakeLLM(script={TASK: [no_questions(), fill(broken), bad, good, explain(solved)]})
    events = run(env, fake, profile_answers=answers())
    assert of(events, "plan")[0]["verdict"] == "valid"
    assert "CMSC 99999 is not a course in the catalog" in str(fake.calls[3]["messages"])


def test_a_locked_course_cannot_be_placed_again(env: Env, solved: list[tuple[str, str]]) -> None:
    """Final review 5: the plan the model writes may not place a locked course a second time."""
    code, term = solved[0]
    other = next(t for _, t in solved if t != term)
    locked = {**STATE, "items": [{"course": code, "term": term, "locked": True}]}
    twice = fill([(code, other), *solved[1:]])
    fake = FakeLLM(script={TASK: [no_questions(), twice, fill(solved), explain(solved)]})
    events = run(env, fake, profile_answers=answers(), plan=locked)
    assert f"{code} is locked or in progress" in str(fake.calls[2]["messages"])
    touched = [o.get("course") for p in of(events, "proposal") for o in p["ops"]]
    assert code not in touched
