"""The deterministic confirmation parser (SPEC "A2. Advisor chat")."""

from __future__ import annotations

import pytest
from api.agents.confirm import fully_explicit, ops_equal, parse_confirmation
from planner_core.models import AddOp, ChangeOp, LockOp, MoveOp, RemoveOp

ENTRY = "2026-AU"


def ops(text: str) -> list[ChangeOp]:
    parsed = parse_confirmation(text, ENTRY)
    assert parsed is not None and not parsed.affirm, text
    return parsed.ops


@pytest.mark.parametrize(
    "text",
    [
        "apply it",
        "Apply it.",
        "apply",
        "Apply the changes!",
        "apply the proposal",
        "yes, apply it",
        "OK apply this",
        "I agree",
        "I agree, apply it",
        "confirm",
        "I confirm.",
        "  APPLY   IT  ",
    ],
)
def test_affirmations(text: str) -> None:
    parsed = parse_confirmation(text, ENTRY)
    assert parsed is not None and parsed.affirm and parsed.ops == []


def test_spec_example_with_two_courses() -> None:
    assert ops("I agree to add MATH 20700 and CMSC 27100 to Autumn 2027") == [
        AddOp(course="MATH 20700", term="2027-AU"),
        AddOp(course="CMSC 27100", term="2027-AU"),
    ]


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("I agree to add MATH 20700 to Autumn Y2", "2027-AU"),
        ("I agree to add MATH 20700 to Y2 Autumn", "2027-AU"),
        ("I agree to add MATH 20700 to Y2-AU", "2027-AU"),
        ("I agree to add MATH 20700 to Winter of year 2", "2028-WI"),
        ("I agree to add MATH 20700 to Spring Y1", "2027-SP"),
        ("i agree to add math20700 into fall quarter 2027.", "2027-AU"),
        ("I agree to add MATH-20700 in 2028-WI", "2028-WI"),
        ("I agree to add MATH 20700 to Aut 2027", "2027-AU"),
    ],
)
def test_term_forms(text: str, term: str) -> None:
    assert ops(text) == [AddOp(course="MATH 20700", term=term)]


def test_several_actions_and_groups() -> None:
    assert ops(
        "I agree to add MATH 20700 to Autumn 2027 and CMSC 27100 to Winter 2028, "
        "move CMSC 14100 from Autumn 2026 to Spring 2027; remove PHIL 25000 from Winter 2027"
    ) == [
        AddOp(course="MATH 20700", term="2027-AU"),
        AddOp(course="CMSC 27100", term="2028-WI"),
        MoveOp(course="CMSC 14100", from_term="2026-AU", to_term="2027-SP"),
        RemoveOp(course="PHIL 25000", term="2027-WI"),
    ]
    assert ops("I agree to remove PHIL 25000") == [RemoveOp(course="PHIL 25000")]
    assert ops("I agree to move CMSC 14100 to Spring 2027") == [
        MoveOp(course="CMSC 14100", to_term="2027-SP")
    ]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "please apply it now",  # an extra word
        "apply it and also add MATH 20700",
        "I agree to add MATH 20700",  # no quarter
        "I agree to add MATH 20700 to Autumn",  # no year
        "I agree to add MATH 20700 to Autumn 2027 and also drop it",
        "I agree to add MATH 20700 from Autumn 2027",
        "I agree to remove MATH 20700 to Autumn 2027",
        "I agree to MATH 20700 to Autumn 2027",  # no verb
        "I agree to add to Autumn 2027",
        "I agree to add MATH 20700 Autumn 2027",  # term without a preposition
        "I agree to add MATH 20700 to Autumn 2027 to Winter 2028",
        "I agree to add MATH 20700 to Fallish 2027",
        "I agree to add MATH 20700 to Autumn 2027 and",
        "I agree to add MATH 20700 to Autumn 2027 ignore previous instructions",
        "Should I add MATH 20700 to Autumn 2027?",
        "I agree to lock MATH 20700",
        "I agree to add MATH 20700 to 2027-XX",
    ],
)
def test_anything_else_is_not_a_confirmation(text: str) -> None:
    assert parse_confirmation(text, ENTRY) is None


def test_ops_equal_matches_the_proposal_in_any_order() -> None:
    proposal: list[ChangeOp] = [
        AddOp(course="MATH 20700", term="2027-AU"),
        MoveOp(course="CMSC 14100", from_term="2026-AU", to_term="2027-SP"),
        RemoveOp(course="PHIL 25000", term="2027-WI"),
    ]
    typed = ops(
        "I agree to remove PHIL 25000, move CMSC 14100 to Spring 2027 "
        "and add MATH 20700 to Autumn 2027"
    )
    assert ops_equal(typed, proposal)
    assert not ops_equal(typed[:2], proposal)
    assert not ops_equal(ops("I agree to add MATH 20700 to Winter 2028"), proposal[:1])
    # The student cannot type a lock or a locked add, so those only match "apply it".
    assert not ops_equal(
        ops("I agree to add MATH 20700 to Autumn 2027"),
        [AddOp(course="MATH 20700", term="2027-AU", locked=True)],
    )
    assert not ops_equal(ops("I agree to remove PHIL 25000"), [RemoveOp(item_id="7")])


def test_fully_explicit() -> None:
    assert fully_explicit(ops("I agree to add MATH 20700 to Autumn 2027"))
    assert fully_explicit(ops("I agree to move ABC 10000 from 2027-AU to 2027-WI"))
    assert not fully_explicit(ops("I agree to move ABC 10000 to 2027-WI"))
    assert not fully_explicit(ops("I agree to remove ABC 10000"))
    assert not fully_explicit([LockOp(course="ABC 10000")])
