"""The dashboard agent's pure logic (no database, no model): the quick replies come from the
question file, the deterministic mapper reads replies into the question's field, and the
grounding filter keeps only answers the student's own words support."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from api.agents import interview as iv
from api.profile_questions import Question, agent_questions, question_set


def q(question_id: str) -> Question:
    found = question_set().question(question_id)
    assert found is not None
    return found


def row(**fields: Any) -> Any:
    """A stand-in for a StudentProfile row (only the attributes the logic reads)."""
    base: dict[str, Any] = {f.field: None for f in agent_questions()}
    base["research_areas"] = []
    return SimpleNamespace(**{**base, **fields})


# ------------------------------------------------------------------------------ quick replies


def test_quick_replies_are_the_file_labels_then_skip() -> None:
    for question in agent_questions():
        chips = iv.quick_replies(question)
        assert chips[-1] == "Skip"
        if question.type in ("single", "multi"):
            assert chips[:-1] == [o.label for o in question.options]
    assert iv.quick_replies(q("post_grad_plan")) == [
        "Work in industry",
        "Graduate school",
        "Medical or law school",
        "Undecided",
        "Skip",
    ]
    assert iv.quick_replies(q("wants_research")) == ["Yes", "No", "Skip"]
    scale = [*(str(n) for n in range(1, 11)), "Skip"]
    assert iv.quick_replies(q("theory_vs_application")) == scale
    assert iv.quick_replies(q("terms_away")) == ["None", "Skip"]
    assert iv.quick_replies(q("research_areas")) == ["Skip"]
    assert iv.quick_replies(None) == []


def test_every_quick_reply_maps_to_an_answer_or_a_skip() -> None:
    for question in agent_questions():
        for chip in iv.quick_replies(question):
            reading = iv.read_reply(question, chip)
            assert reading.kind == ("skip" if chip == "Skip" else "answer"), (question.id, chip)


# ------------------------------------------------------------------------------ the mapper


@pytest.mark.parametrize(
    ("question_id", "reply", "value"),
    [
        ("post_grad_plan", "Graduate school", "grad_school"),
        ("post_grad_plan", "GRADUATE SCHOOL", "grad_school"),
        ("post_grad_plan", "grad school", "grad_school"),
        ("post_grad_plan", "I want a PhD", "grad_school"),
        ("post_grad_plan", "work in industry", "industry"),
        ("post_grad_plan", "not sure", "undecided"),
        ("pace", "On time", "on_time"),
        ("pace", "no rush", "flexible"),
        ("wants_research", "Yes", True),
        ("wants_research", "yeah, definitely", True),
        ("wants_research", "no", False),
        ("wants_research", "I'm not interested", False),
        ("course_load", "Conservative", "conservative"),
        ("course_load", "just enough to stay full time", "conservative"),
        ("course_load", "a normal load", "normal"),
        ("course_load", "a mix of 3 and 4 courses", "normal"),
        ("course_load", "Ambitious", "ambitious"),
        ("course_load", "as heavy as I can", "ambitious"),
        # A named option after "not" is not the answer (spec review, 2026-11-25).
        ("course_load", "not ambitious, just normal", "normal"),
        ("pace", "on time, not early", "on_time"),
        ("theory_vs_application", "7", 7),
        ("theory_vs_application", "7/10", 7),
        ("theory_vs_application", "seven out of 10", 7),
        ("class_formats", "Seminar", ["seminar"]),
        ("class_formats", "seminars and labs", ["seminar", "lab"]),
        ("class_formats", "lectures, not labs", ["lecture"]),
        ("class_formats", "all of them", ["seminar", "lecture", "lab", "online"]),
        ("class_formats", "None", []),
        ("terms_away", "None", []),
        ("terms_away", "no, I'll stay on campus", []),
        ("terms_away", "autumn 2027 abroad", [{"term": "2027-AU", "kind": "abroad"}]),
        ("terms_away", "fall '27, study abroad", [{"term": "2027-AU", "kind": "abroad"}]),
        ("terms_away", "2028-WI leave", [{"term": "2028-WI", "kind": "leave"}]),
        (
            "terms_away",
            "Study abroad in autumn 2027 and an internship in summer 2028",
            [{"term": "2027-AU", "kind": "abroad"}, {"term": "2028-SU", "kind": "internship"}],
        ),
        (
            "research_areas",
            "machine learning theory, ancient Mediterranean trade and condensed matter",
            ["Machine learning theory", "Ancient Mediterranean trade", "Condensed matter"],
        ),
    ],
)
def test_read_reply_maps_answers(question_id: str, reply: str, value: Any) -> None:
    reading = iv.read_reply(q(question_id), reply)
    assert reading.kind == "answer", reading
    assert reading.value == value


@pytest.mark.parametrize(
    ("question_id", "reply"),
    [
        ("post_grad_plan", "pizza"),
        ("post_grad_plan", "grad school or industry"),  # two options: ask again
        ("wants_research", "yes, no"),
        ("course_load", "pizza"),
        ("course_load", "normal or ambitious"),  # two options: ask again
        ("course_load", "not too heavy"),
        ("course_load", "nothing too heavy please"),
        ("course_load", "I don't want to overload"),
        ("course_load", "not ambitious"),
        ("course_load", "max 4 courses"),
        ("theory_vs_application", "11"),
        ("theory_vs_application", "mostly theory"),  # not a number
        ("class_formats", "pizza"),
        ("terms_away", "autumn and winter 2027 abroad"),  # which year is autumn?
        ("terms_away", "autumn 2027"),  # no reason
        ("terms_away", "next fall abroad"),  # no year
    ],
)
def test_read_reply_asks_again_when_it_cannot_map(question_id: str, reply: str) -> None:
    assert iv.read_reply(q(question_id), reply).kind == "unclear"


@pytest.mark.parametrize(
    ("question_id", "reply"),
    [
        ("pace", "Skip"),
        ("pace", "skip this one"),
        ("terms_away", "pass"),
        ("wants_research", "no idea"),
        ("pace", "not sure"),
        ("research_areas", "none"),
    ],
)
def test_read_reply_skips(question_id: str, reply: str) -> None:
    assert iv.read_reply(q(question_id), reply).kind == "skip"


# ------------------------------------------------------------------------------ grounding


def test_proposed_patch_keeps_only_supported_answers() -> None:
    areas = q("research_areas")
    patch = iv.proposed_patch(areas, ["Quantum computing", "Opera"], "quantum stuff", row())
    assert patch is not None and patch.research_areas == ["Quantum computing"]
    assert iv.proposed_patch(areas, ["Opera"], "quantum stuff", row()) is None
    # Merged with the record, case-insensitively.
    patch = iv.proposed_patch(
        areas,
        ["quantum computing", "Lasers"],
        "quantum and lasers",
        row(research_areas=["Quantum computing"]),
    )
    assert patch is not None and patch.research_areas == ["Quantum computing", "Lasers"]

    plan = q("post_grad_plan")
    assert iv.proposed_patch(plan, "astronaut", "astronaut", row()) is None  # not an option
    # The model's choice must be one the words name when they name any.
    assert iv.proposed_patch(plan, "med_law", "grad school or industry", row()) is None
    patch = iv.proposed_patch(plan, "industry", "grad school or industry", row())
    assert patch is not None and patch.post_grad_plan == "industry"

    load = q("course_load")
    assert iv.proposed_patch(load, "heavy", "heavy", row()) is None  # not an option
    assert iv.proposed_patch(load, "ambitious", "a normal load", row()) is None
    patch = iv.proposed_patch(load, "normal", "a normal load", row())
    assert patch is not None and patch.course_load == "normal"

    away = q("terms_away")
    said = "next fall abroad"
    patch = iv.proposed_patch(away, [{"term": "2027-AU", "kind": "abroad"}], said, row())
    assert patch is not None and patch.terms_away is not None
    assert patch.terms_away[0].term == "2027-AU"
    assert iv.proposed_patch(away, [{"term": "2027-AU", "kind": "abroad"}], "hmm", row()) is None
    assert iv.proposed_patch(away, [], "I am not sure", row()) is None
    assert iv.proposed_patch(away, [{"term": "2027-FA", "kind": "abroad"}], said, row()) is None

    formats = q("class_formats")
    assert iv.proposed_patch(formats, ["online"], "seminars please", row()) is None
    assert iv.proposed_patch(formats, ["podcast"], "podcast", row()) is None


def test_grounding_rules() -> None:
    said = "I like ML, philosophical questions and quantum stuff"
    assert iv.grounded("Machine learning", said)
    assert iv.grounded("Philosophy", said)
    assert iv.grounded("Quantum computing", said)
    assert not iv.grounded("Opera", said)
    assert not iv.grounded("AI", "I said nothing about it")
    assert iv.grounded("AI", "AI and society")


def test_the_turn_schema_uses_the_file_options_and_has_no_quick_replies() -> None:
    schema = iv.turn_schema()
    assert "quick_replies" not in schema["properties"]
    assert "portrait" not in schema["properties"]
    facts = schema["properties"]["facts"]["properties"]
    assert set(facts) == {x.field for x in agent_questions()}
    plan = facts["post_grad_plan"]["anyOf"][0]["enum"]
    assert plan == [o.value for o in q("post_grad_plan").options]
    topics = schema["properties"]["topic"]["enum"]
    assert topics == [*(x.id for x in agent_questions()), "wrapup"]
