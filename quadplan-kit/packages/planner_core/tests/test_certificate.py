"""The trusted checker: what it accepts, what it rejects, and `verify_checked`."""

import ast
import inspect
import sys
from typing import Any

import pytest
from core_support import T, catalog, course, error_codes, found, plan, program, ruleset
from planner_core import (
    certificate,
    certificate_problems,
    check_certificate,
    verify,
    verify_checked,
)
from planner_core.models import Certificate, PlanState, Requisite, VerifyOptions

OPTS = VerifyOptions(checks=["V01", "V02", "V03", "V07"])
CAT = catalog(
    [
        "FAKE 10000",
        "FAKE 10100",
        "FAKE 20000",
        "FAKE 20100",
        "FAKE 20200",
        "FAKE 20300",
        course("BIGG 20000", units=200),
        "NOTE 10000",
    ]
)
PROGRAM = program(
    "fake-ba",
    {
        "group": {
            "all": True,
            "children": [
                {"id": "intro", "slot": {"any_of": ["FAKE 10000"]}},
                {
                    "id": "electives",
                    "select": {
                        "count": 2,
                        "from": {"subject": "FAKE", "number_range": [20000, 29999]},
                    },
                },
            ],
        },
        "constraints": {"min_grade": "C-"},
    },
)
RULES = ruleset(
    PROGRAM,
    prereqs={
        "FAKE 10100": {"all": ["FAKE 10000", {"placement": "FAKE 20300"}, {"program": "fake-*"}]},
        "FAKE 20000": {"any": [{"standing": "second-year"}, {"consent": "instructor"}]},
    },
    requisites=[Requisite(course="NOTE 10000", raw_text="Open to all students.")],
)
PLAN = plan(
    {T[0]: ["FAKE 10000", "NOTE 10000"], T[1]: ["FAKE 10100"], T[3]: ["FAKE 20000", "FAKE 20100"]},
    programs=["fake-ba"],
    credits=[{"kind": "placement", "label": "Fake placement", "maps_to": "FAKE 20300"}],
)


def cert_of(p: PlanState = PLAN) -> dict[str, Any]:
    report = verify(p, RULES, CAT, OPTS)
    assert report.certificate is not None, report.issues
    assert certificate_problems(p, RULES, CAT, report.certificate) == []
    return report.certificate.model_dump()


def problems(raw: dict[str, Any], p: PlanState = PLAN) -> str:
    cert = Certificate.model_validate(raw)
    found_problems = certificate_problems(p, RULES, CAT, cert)
    assert check_certificate(p, RULES, CAT, cert) == (not found_problems)
    return " | ".join(found_problems)


def test_the_certificate_has_the_shape_of_the_spec() -> None:
    raw = cert_of()
    assert raw["plan_hash"].startswith("sha256:")
    assert list(raw["rules"]) == ["fake-ba@2026-27"]
    assert raw["assignments"] == [
        {"node": "fake-ba/electives", "courses": ["FAKE 20000", "FAKE 20100"]},
        {"node": "fake-ba/intro", "courses": ["FAKE 10000"]},
    ]
    assert raw["prereq_witnesses"] == [
        {
            "course": "FAKE 10100",
            "term": T[1],
            "by": ["FAKE 10000@2026-AU", "placement:FAKE 20300", "program:fake-*"],
        },
        {"course": "FAKE 20000", "term": T[3], "by": ["standing:second-year"]},
    ]
    assert raw["loads"] == [
        {"term": T[0], "units": 200},
        {"term": T[1], "units": 100},
        {"term": T[3], "units": 200},
    ]
    assert problems(raw) == ""


def test_rejects_wrong_plan_or_rules() -> None:
    raw = cert_of()
    assert "plan_hash does not match" in problems(
        raw, PLAN.model_copy(update={"placements": ["x"]})
    )
    assert "rule hashes do not match" in problems({**raw, "rules": {"fake-ba@2026-27": "sha256:0"}})
    assert "rule hashes do not match" in problems({**raw, "rules": {}})
    unlisted = PLAN.model_copy(
        update={"programs": [*PLAN.programs, *plan(programs=["other"]).programs]}
    )
    assert "no rules for program other" in " | ".join(
        certificate_problems(unlisted, RULES, CAT, Certificate.model_validate(raw))
    )


def test_rejects_bad_assignments() -> None:
    raw = cert_of()
    twice = {**raw, "assignments": [*raw["assignments"], raw["assignments"][0]]}
    assert "fake-ba/electives is assigned twice" in problems(twice)
    alien = {
        **raw,
        "assignments": [*raw["assignments"], {"node": "fake-ba/nope", "courses": ["FAKE 20000"]}],
    }
    assert "fake-ba/nope is not a unit of the plan's programs" in problems(alien)
    listed_twice = cert_of()
    listed_twice["assignments"][0]["courses"] = ["FAKE 20000", "FAKE 20000"]
    assert "not in the plan, or is listed twice" in problems(listed_twice)
    wrong = cert_of()
    wrong["assignments"][0]["courses"] = ["FAKE 20000", "FAKE 10100"]
    assert "FAKE 10100 does not match the selector" in problems(wrong)
    empty = cert_of()
    empty["assignments"] = empty["assignments"][:1]
    assert "fake-ba is not satisfied by the assignments" in problems(empty)
    reused = cert_of()
    reused["assignments"][1]["node"] = "fake-ba/electives"
    reused["assignments"][0]["node"] = "fake-ba/intro"
    assert "does not match the selector" in problems(reused)


def test_rejects_a_course_below_the_grade_minimum() -> None:
    low = plan(
        {
            T[0]: ["FAKE 10000"],
            T[3]: [
                "FAKE 20000",
                "FAKE 20100",
                {"course": "FAKE 20200", "status": "completed", "grade": "D"},
            ],
        },
        programs=["fake-ba"],
    )
    raw = cert_of(low)
    assert raw["assignments"][0]["courses"] == ["FAKE 20000", "FAKE 20100"]  # the D is not used
    raw["assignments"][0]["courses"] = ["FAKE 20000", "FAKE 20200"]
    assert "FAKE 20200 is below the grade minimum" in problems(raw, low)


def test_rejects_bad_witnesses() -> None:
    raw = cert_of()
    missing = {**raw, "prereq_witnesses": raw["prereq_witnesses"][:1]}
    assert "no prerequisite witness for FAKE 20000@2027-AU" in problems(missing)
    for token in (
        "placement:OTHER 10000",
        "standing:fourth-year",
        "program:math-*",
        "FAKE 10000@2027-SP",
        "credit:FAKE 10000",
        "nonsense",
    ):
        forged = cert_of()
        forged["prereq_witnesses"][0]["by"] = [
            "FAKE 10000@2026-AU",
            "placement:FAKE 20300",
            "program:fake-*",
            token,
        ]
        assert "cites something that is not in the plan" in problems(forged), token
    for dropped in range(3):
        weak = cert_of()
        del weak["prereq_witnesses"][0]["by"][dropped]
        assert "does not satisfy its requisite" in problems(weak)
    # consent is always a fact, and it satisfies the `any`
    consent = cert_of()
    consent["prereq_witnesses"][1]["by"] = ["consent:instructor"]
    assert problems(consent) == ""
    # a witness in the same term does not satisfy a strict prerequisite
    same_term = plan(
        {T[1]: ["FAKE 10000", "FAKE 10100"], T[3]: ["FAKE 20000", "FAKE 20100"]},
        programs=["fake-ba"],
        placements=["FAKE 20300"],
    )
    forged = cert_of()
    forged["plan_hash"] = verify(same_term, RULES, CAT).plan_hash
    forged["prereq_witnesses"][0]["by"][0] = "FAKE 10000@2027-WI"
    forged["loads"] = [{"term": T[1], "units": 200}, {"term": T[3], "units": 200}]
    assert (
        problems(forged, same_term)
        == "the witness for FAKE 10100@2027-WI does not satisfy its requisite"
    )


def test_rejects_wrong_loads() -> None:
    raw = cert_of()
    assert "loads do not match" in problems({**raw, "loads": raw["loads"][:2]})
    doubled = {**raw, "loads": [*raw["loads"], raw["loads"][0]]}
    assert "loads do not match" in problems(doubled)


def test_bounded_parts_by_units_and_overlapping_parts() -> None:
    rules = ruleset(
        program(
            "p",
            {
                "group": {
                    "n_of": 1,
                    "children": [
                        {
                            "id": "a",
                            "group": {
                                "n_of": 1,
                                "children": [
                                    {
                                        "id": "bp",
                                        "bounded_parts": {
                                            "total": {"units": 400},
                                            "parts": [
                                                {
                                                    "id": "x",
                                                    "from": {"subject": "FAKE"},
                                                    "count": [1, 2],
                                                },
                                                {
                                                    "id": "y",
                                                    "from": {"number_range": [20000, 29999]},
                                                    "count": [1, 2],
                                                },
                                            ],
                                        },
                                    },
                                    {"id": "never", "slot": {"any_of": ["NOTE 10000"]}},
                                ],
                            },
                        },
                        {"id": "b", "slot": {"any_of": ["NOTE 10000"]}},
                    ],
                }
            },
        )
    )
    p = plan({T[0]: ["FAKE 20000", "FAKE 20100", "BIGG 20000"]}, programs=["p"])
    report = verify(p, rules, CAT, OPTS)
    assert report.status == "valid" and report.certificate is not None
    assert check_certificate(p, rules, CAT, report.certificate)
    used = {a.node: a.courses for a in report.certificate.assignments}
    assert sorted(c for courses in used.values() for c in courses) == [
        "BIGG 20000",
        "FAKE 20000",
        "FAKE 20100",
    ]
    rows = {r.node_id: (r.satisfied, r.have, r.need, r.unit) for r in report.progress}
    assert rows["p/a/bp"] == (True, 400, 400, "units")
    # the same course in two parts is rejected
    raw = report.certificate.model_dump()
    raw["assignments"] = [
        {"node": "p/a/bp/x", "courses": ["FAKE 20000", "FAKE 20100"]},
        {"node": "p/a/bp/y", "courses": ["FAKE 20000", "BIGG 20000"]},
    ]
    assert not check_certificate(p, rules, CAT, Certificate.model_validate(raw))
    short = plan({T[0]: ["FAKE 20000", "BIGG 20000"]}, programs=["p"])
    report = verify(short, rules, CAT, OPTS)
    assert error_codes(report) == {"V07"}
    assert "0 of 1 required parts are complete" in found(report, "V07")[0].message
    rows = {r.node_id: (r.satisfied, r.have, r.need, r.unit) for r in report.progress}
    assert rows["p/a/bp"] == (False, 300, 400, "units")


def test_a_broken_certificate_is_rejected_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object) -> list[str]:
        raise RuntimeError("bug in the checker")

    monkeypatch.setattr(certificate, "certificate_problems", boom)
    assert check_certificate(PLAN, RULES, CAT, Certificate.model_validate(cert_of())) is False


def test_verify_checked_enforces_the_hard_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    report, found_problems = verify_checked(PLAN, RULES, CAT, OPTS)
    assert found_problems == [] and report.status == "valid" and report.certificate is not None
    hidden, _ = verify_checked(
        PLAN, RULES, CAT, OPTS.model_copy(update={"include_certificate": False})
    )
    assert hidden.status == "valid" and hidden.certificate is None
    # a restricted run cannot prove validity
    partial, _ = verify_checked(PLAN, RULES, CAT, VerifyOptions(checks=["V01", "V02"]))
    assert partial.status == "warnings" and partial.certificate is None
    assert "Partial check" in partial.issues[-1].message
    # errors stay errors
    bad, _ = verify_checked(plan(programs=["fake-ba"]), RULES, CAT, OPTS)
    assert bad.status == "errors" and bad.certificate is None
    # a rejected certificate: dropped, status errors, problems returned for the alert
    verify_module = sys.modules["planner_core.verify"]  # the name is shadowed by the function
    monkeypatch.setattr(verify_module, "certificate_problems", lambda *a: ["made-up problem"])
    rejected, found_problems = verify_checked(PLAN, RULES, CAT, OPTS)
    assert found_problems == ["made-up problem"]
    assert rejected.status == "errors" and rejected.certificate is None
    assert "Internal check failed" in rejected.issues[-1].message


def test_the_checker_is_small_and_solver_free() -> None:
    source = inspect.getsource(certificate)
    assert len(source.splitlines()) <= 300
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not any("ortools" in (name or "") or "solver" in (name or "") for name in imported)
    assert not {"planner_core.programs", "planner_core.checks", "planner_core.verify"} & imported
