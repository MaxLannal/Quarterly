"""The planner agent's event contract (docs/CONTRACTS.md, "Planner agent") and its citations."""

from __future__ import annotations

from typing import Any

import pytest
from api.agents.runtime import checked_citations, citable_ids, citation_label
from api.schemas.planner import PlannerEvent, PlannerRequest
from pydantic import TypeAdapter, ValidationError

ADAPTER: TypeAdapter[Any] = TypeAdapter(PlannerEvent)
ADD = {"op": "add", "course": "CMSC 14100", "term": "2026-AU"}
VERDICT = {
    "status_after": "warnings",
    "status_before": "errors",
    "new_issues": [],
    "resolved_issues": 2,
}

EVENTS: list[dict[str, Any]] = [
    {"type": "step", "name": "Writing your plan", "status": "started"},
    {
        "type": "question",
        "run_id": "r1",
        "question_id": "interests",
        "field": "interests",
        "text": "Which subjects or topics interest you most?",
        "options": [],
    },
    {
        "type": "plan",
        "run_id": "r1",
        "verdict": "valid",
        "issues": [{"code": "S01", "level": "error", "message": "A course in a quarter away."}],
        "compromises": [{"rule": "G29", "tier": "preference", "why": "x", "traded": "y"}],
        "summary": "A CS BS plan.",
    },
    {
        "type": "proposal",
        "change_set_id": None,
        "group_id": "g1",
        "title": "Introductory CS sequence",
        "kind": "major",
        "ops": [ADD],
        "why": "You said you want machine learning.",
        "citations": [{"kind": "profile", "id": "interests", "label": "Your interests"}],
        "rules": [{"id": "G38", "text": "Start the introductory sequence in year 1."}],
        "preview": VERDICT,
    },
    {"type": "message", "text": "Done.", "citations": []},
    {"type": "done", "run_id": "r1", "working_notes": "- 2026-11-26 · avoid · x"},
    {"type": "error", "message": "Start again.", "reason": "expired"},
]


@pytest.mark.parametrize("event", EVENTS, ids=[e["type"] for e in EVENTS])
def test_planner_event_round_trip(event: dict[str, Any]) -> None:
    parsed = ADAPTER.validate_python(event)
    assert ADAPTER.validate_python(ADAPTER.dump_python(parsed, mode="json")) == parsed
    assert ADAPTER.dump_python(parsed, mode="json")["type"] == event["type"]


def test_planner_request_needs_a_mode_and_forbids_unknown_fields() -> None:
    plan = {"catalog_year": "2026-27", "entry_term": "2026-AU"}
    req = PlannerRequest.model_validate({"mode": "generate", "plan": plan})
    assert req.history == [] and req.pending == [] and req.profile_answers == {}
    with pytest.raises(ValidationError):
        PlannerRequest.model_validate({"mode": "generate", "plan": plan, "variants": 2})
    with pytest.raises(ValidationError):
        PlannerRequest.model_validate({"mode": "plan", "plan": plan})


def test_checked_citations_profile_and_guideline() -> None:
    seen = citable_ids(profile_fields={"interests"}, guideline_ids={"G07"})
    cited = [
        ("profile", "pace", ""),
        ("profile", "interests", "model label"),
        ("guideline", "G99", ""),
        ("guideline", "G07", ""),
    ]
    kept = checked_citations("a1_planner_agent", cited, seen)
    assert [(c.kind, c.id) for c in kept] == [("profile", "interests"), ("guideline", "G07")]
    assert [c.label for c in kept] == ["Your interests", "Guideline G07"]


def test_citation_label_for_profile_uses_the_question_label() -> None:
    assert citation_label("profile", "course_load") == "Your course load"
    assert citation_label("profile", "not_a_field") == "Your record"
