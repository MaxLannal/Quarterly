"""The student record (Issue #14) through `GET/PATCH /me/profile`, the question file
(`GET /profile/questions`), `student.md` (`GET /me/profile/export.md`) and the export helper:
login required, the row created lazily, the email read from the account and never stored,
validation, true partial updates, and a fixed student.md that never contains the email or the
username."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from api.db import models as m
from api.profile_data import export_profile
from api.profile_questions import question_set
from auth_test_support import Env
from test_profile_support import account_id, db_url_fixture, env_fixture, login  # noqa: F401

pytestmark = pytest.mark.db

REPO = Path(__file__).resolve().parents[3]
STEP_2 = [
    "post_grad_plan",
    "pace",
    "wants_research",
    "research_areas",
    "courses_per_term",
    "terms_away",
    "class_formats",
    "theory_vs_application",
]
FULL: dict[str, Any] = {
    "class_year": 2028,
    "expected_graduation_term": "2028-SP",
    "intended_programs": ["phys-bs"],
    "entry_term": "2025-AU",
    "entry_year_level": 2,
    "credits": [
        {"kind": "AP", "label": "  AP Physics C ", "maps_to": "PHYS 13100", "units": 100},
        {"kind": "transfer", "label": "Calculus at a community college", "units": 100},
    ],
    "taken_courses": [
        {"course": "CMSC 14100", "term": "2025-AU", "status": "completed", "grade": "A-"},
        {"course": "cmsc14200", "term": "2026-WI", "status": "in_progress"},
    ],
    "post_grad_plan": "grad_school",
    "pace": "on_time",
    "wants_research": True,
    "research_areas": ["  Quantum materials ", "quantum materials", "Machine learning theory"],
    "courses_per_term": 3,
    "terms_away": [{"term": "2027-AU", "kind": "abroad"}],
    "class_formats": ["seminar", "lab", "seminar"],
    "theory_vs_application": 7,
}


def patch(env: Env, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return env.client.patch("/me/profile", json=body, headers=headers)


def test_everything_needs_login(env: Env) -> None:
    assert env.client.get("/me/profile").status_code == 401
    assert env.client.patch("/me/profile", json={"class_year": 2029}).status_code == 401
    assert env.client.get("/me/profile/export.md").status_code == 401
    assert env.client.get("/me/routes").status_code == 401
    assert env.client.post("/agents/interview", json={"mode": "start"}).status_code == 401


def test_the_questions_are_public_and_come_from_the_question_file(env: Env) -> None:
    resp = env.client.get("/profile/questions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [g["title"] for g in body["groups"]] == [
        "Academic background",
        "Goals",
        "Scheduling",
        "Learning preferences",
    ]
    assert [q["id"] for q in body["questions"] if q["step"] == 2] == STEP_2
    post_grad = next(q for q in body["questions"] if q["id"] == "post_grad_plan")
    assert [o["value"] for o in post_grad["options"]] == [
        "industry",
        "grad_school",
        "med_law",
        "undecided",
    ]
    # Max's #14 D2: no freeform interests or humanities question.
    assert not {"interests", "humanities"} & {q["id"] for q in body["questions"]}


def test_the_mock_copy_of_the_question_file_is_current() -> None:
    mock = json.loads((REPO / "apps/web/src/mocks/questions.json").read_text())
    assert mock == question_set().model_dump(mode="json"), "run `make api-client`"


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
    assert body["member_since"] and body["completeness"] == 0 and body["answered"] == []
    assert body["terms_away"] is None and body["class_formats"] is None
    assert resp.headers["cache-control"] == "no-store"
    with env.db() as db:
        row = db.get(m.StudentProfile, me)
        assert row is not None
        # Decision 5: the email lives only in account.email.
        values = [getattr(row, c.key) for c in sa.inspect(m.StudentProfile).mapper.column_attrs]
        assert "@" not in repr(values)


def test_patch_saves_the_general_information(env: Env) -> None:
    headers = login(env)
    resp = patch(env, headers, FULL)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["programs"] == [{"id": "phys-bs", "name": "Physics (BS)"}]
    assert body["credits"] == [
        {"kind": "AP", "label": "AP Physics C", "maps_to": "PHYS 13100", "units": 100},
        {
            "kind": "transfer",
            "label": "Calculus at a community college",
            "maps_to": None,
            "units": 100,
        },
    ]
    assert body["taken_courses"] == [
        {
            "course": "CMSC 14100",
            "title": "Introduction to Computer Science I",
            "term": "2025-AU",
            "status": "completed",
            "grade": "A-",
            "grading": "letter",
            "units": None,
            "locked": False,
        },
        {
            "course": "CMSC 14200",
            "title": "Introduction to Computer Science II",
            "term": "2026-WI",
            "status": "in_progress",
            "grade": None,
            "grading": "letter",
            "units": None,
            "locked": False,
        },
    ]
    assert body["research_areas"] == ["Quantum materials", "Machine learning theory"]
    assert body["terms_away"] == [{"term": "2027-AU", "kind": "abroad"}]
    assert body["class_formats"] == ["seminar", "lab"]
    assert set(body["answered"]) == {q.id for q in question_set().questions}
    assert body["completeness"] == 1.0


@pytest.mark.parametrize(
    "bad",
    [
        {"class_year": 2019},
        {"expected_graduation_term": "2029-XX"},
        {"entry_year_level": 5},
        {"post_grad_plan": "astronaut"},
        {"pace": "slow"},
        {"courses_per_term": 9},
        {"theory_vs_application": 0},
        {"terms_away": [{"term": "2027-AU", "kind": "vacation"}]},
        {"class_formats": ["podcast"]},
        {"credits": [{"kind": "IB", "label": "IB Physics"}]},
        {"credits": [{"kind": "AP", "label": "AP Fake", "maps_to": "NOPE 10000"}]},
        {"taken_courses": [{"course": "NOPE 10000", "term": "2025-AU"}]},
        {"research_areas": ["x" * 61]},
        {"feed_categories": [f"cat{i}" for i in range(17)]},
        {"intended_programs": ["nope-ba"]},
        {"interview": {"turns": [{"role": "guide", "text": "z" * 2001}]}},
        # The old freeform fields are gone (Issue #14 D2): unknown fields are ignored, so check
        # that they are not stored instead (below).
    ],
)
def test_patch_validation(env: Env, bad: dict[str, Any]) -> None:
    headers = login(env)
    assert patch(env, headers, bad).status_code == 422


def test_old_freeform_fields_are_not_kept(env: Env) -> None:
    headers = login(env)
    body = patch(env, headers, {"interests": ["Physics"], "portrait": {"headline": "x"}}).json()
    assert "interests" not in body and "portrait" not in body


def test_patch_is_partial_and_null_clears(env: Env) -> None:
    headers = login(env)
    patch(env, headers, FULL)
    body = patch(env, headers, {"pace": "early"}).json()
    assert body["pace"] == "early" and body["class_year"] == 2028
    assert len(body["credits"]) == 2 and len(body["taken_courses"]) == 2
    body = patch(env, headers, {"class_year": None, "terms_away": [], "credits": []}).json()
    assert body["class_year"] is None and body["credits"] == []
    # An empty list is an answer ("none"); null is "not answered".
    assert body["terms_away"] == [] and "terms_away" in body["answered"]
    assert "class_year" not in body["answered"]
    body = patch(env, headers, {"terms_away": None}).json()
    assert body["terms_away"] is None and "terms_away" not in body["answered"]
    body = patch(
        env, headers, {"follows": {"threads": [3, 3, 4], "courses": ["PHYS 13100"]}}
    ).json()
    assert body["follows"] == {"threads": [3, 4], "courses": ["PHYS 13100"]}
    assert len(body["taken_courses"]) == 2


def test_taken_courses_keep_pass_fail_units_and_lock(env: Env) -> None:
    """Blocker 2 (review of PR #21): the profile save keeps a taken course's grading, units and
    lock, and a course sent without them gets the defaults (letter grade, catalog units, not
    locked)."""
    headers = login(env)
    sent = [
        {
            "course": "CMSC 14100",
            "term": "2025-AU",
            "status": "completed",
            "grading": "pass_fail",
            "units": 50,
            "locked": True,
        },
        {"course": "CMSC 14200", "term": "2026-WI", "status": "in_progress"},
    ]
    resp = patch(env, headers, {"taken_courses": sent})
    assert resp.status_code == 200, resp.text
    for body in (resp.json(), env.client.get("/me/profile").json()):
        rows = [(c["course"], c["grading"], c["units"], c["locked"]) for c in body["taken_courses"]]
        assert rows == [
            ("CMSC 14100", "pass_fail", 50, True),
            ("CMSC 14200", "letter", None, False),
        ]
    assert (
        patch(env, headers, {"taken_courses": [{**sent[0], "grading": "audit"}]}).status_code == 422
    )
    # student.md says so too: a rule that needs a letter grade does not count the course.
    lines = env.client.get("/me/profile/export.md").text.splitlines()
    assert next(line for line in lines if "CMSC 14100" in line).endswith(", Pass/Fail")
    assert not next(line for line in lines if "CMSC 14200" in line).endswith("Pass/Fail")


def test_saying_no_to_research_clears_the_areas(env: Env) -> None:
    headers = login(env)
    patch(env, headers, {"wants_research": True, "research_areas": ["Topology"]})
    body = patch(env, headers, {"wants_research": False}).json()
    assert body["research_areas"] == []
    # research_areas only applies to a student who wants research.
    assert "research_areas" not in body["answered"]


def test_csrf_is_required_for_writes(env: Env) -> None:
    login(env)
    assert env.client.patch("/me/profile", json={"class_year": 2029}).status_code == 403


def test_student_md_is_a_download_without_the_email_or_username(env: Env) -> None:
    headers = login(env, "quiet-heron", email="heron.q@uchicago.edu")
    patch(env, headers, {**FULL, "working_notes": "Main: I prefer Philosophical Perspectives."})
    resp = env.client.get("/me/profile/export.md")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/markdown")
    assert 'filename="student.md"' in resp.headers["content-disposition"]
    text = resp.text
    assert "heron" not in text and "@" not in text
    assert "## General Information" in text and "## Working information" in text
    assert "- Taken courses:\n  - 2025-AU CMSC 14100 Introduction to Computer Science I:" in text
    assert "- Quarters away:\n  - Autumn 2027 (2027-AU): Study abroad" in text
    assert "- Theory or application: 7 of 10 (1 = Theory, 10 = Application)" in text
    assert "Main: I prefer Philosophical Perspectives." in text


def test_student_md_has_a_fixed_order_and_says_not_answered(env: Env) -> None:
    login(env)
    empty = env.client.get("/me/profile/export.md").text
    headings = [line for line in empty.splitlines() if line.startswith("#")]
    assert headings == [
        "# Student record",
        "## General Information",
        "### Academic background",
        "### Goals",
        "### Scheduling",
        "### Learning preferences",
        "## Working information",
    ]
    answers = [line for line in empty.splitlines() if line.startswith("- ")]
    assert answers == [f"- {q.label}: Not answered" for q in question_set().questions]


def test_export_profile_has_the_record_without_the_email(env: Env) -> None:
    headers = login(env, "quiet-heron", email="heron.q@uchicago.edu")
    me = account_id(env, "quiet-heron")
    with env.db() as db:
        assert export_profile(db, me) == {"profile": None, "routes": []}
    patch(env, headers, FULL)
    with env.db() as db:
        out = export_profile(db, me)
    profile = out["profile"]
    assert profile["class_year"] == 2028 and profile["pace"] == "on_time"
    assert profile["taken_courses"][0] == {
        "course": "CMSC 14100",
        "term": "2025-AU",
        "status": "completed",
        "grade": "A-",
        "grading": "letter",
        "units": None,
        "locked": False,
    }
    assert profile["student_md"].startswith("# Student record\n")
    assert "heron" not in repr(out) and "@" not in repr(out)
