"""FEEDBACK "Allow Summer Sequences" (Richard, 2026-11-16): the Summer quarter is split into
sessions, so a sequence can run inside one Summer quarter. A prerequisite in the same Summer
quarter counts; a skipped course is still missing; other quarters are unchanged."""

from typing import Any

from core_support import catalog, found, plan, ruleset
from planner_core import check_certificate, verify, verify_checked
from planner_core.terms import is_summer


def needs(code: str) -> Any:
    return code  # the DSL: a bare course code is a `course` prerequisite


CATALOG = catalog(["HUMA 11500", "HUMA 11600", "HUMA 11700"])
RULES = ruleset(prereqs={"HUMA 11600": needs("HUMA 11500"), "HUMA 11700": needs("HUMA 11600")})


def test_is_summer() -> None:
    assert is_summer("2027-SU") and not is_summer("2027-SP") and not is_summer(None)


def test_a_whole_sequence_in_one_summer_is_allowed_and_certified() -> None:
    p = plan({"2027-SU": ["HUMA 11500", "HUMA 11600", "HUMA 11700"]})
    report, problems = verify_checked(p, RULES, CATALOG)
    assert not found(report, "V03", "error") and not problems
    assert report.certificate is not None
    assert check_certificate(p, RULES, CATALOG, report.certificate)


def test_skipping_a_course_in_the_summer_is_still_an_error() -> None:
    p = plan({"2027-SU": ["HUMA 11500", "HUMA 11700"]})
    errors = found(verify(p, RULES, CATALOG), "V03", "error")
    assert [i.course_ids[0] for i in errors] == ["HUMA 11700"]


def test_other_quarters_still_need_an_earlier_quarter() -> None:
    p = plan({"2027-WI": ["HUMA 11500", "HUMA 11600"]})
    errors = found(verify(p, RULES, CATALOG), "V03", "error")
    assert [i.course_ids[0] for i in errors] == ["HUMA 11600"]


def test_the_checker_does_not_accept_a_same_quarter_witness_outside_summer() -> None:
    """A certificate made for a Summer plan stops holding once the pair moves to Winter."""
    summer = plan({"2027-SU": ["HUMA 11500", "HUMA 11600"]})
    report = verify(summer, RULES, CATALOG)
    assert report.certificate is not None
    winter = plan({"2027-WI": ["HUMA 11500", "HUMA 11600"]})
    moved = report.certificate.model_copy(
        update={
            "plan_hash": verify(winter, ruleset(), CATALOG).plan_hash,
            "prereq_witnesses": [
                w.model_copy(update={"term": "2027-WI"})
                for w in report.certificate.prereq_witnesses
            ],
            "loads": [e.model_copy(update={"term": "2027-WI"}) for e in report.certificate.loads],
        }
    )
    assert not check_certificate(winter, RULES, CATALOG, moved)
