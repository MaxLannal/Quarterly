"""V09 (graduation) and V10 (timing) on fake fixtures."""

from typing import Any

from core_support import T, catalog, college, course, error_codes, found, plan, program, ruleset
from planner_core import check_certificate, verify
from planner_core.models import PlanState, Report, VerifyOptions

V09 = VerifyOptions(checks=["V09"])
V10 = VerifyOptions(checks=["V10"])
FILL = [f"FILL {10000 + i}" for i in range(48)]
CAT = catalog(
    [
        *FILL,
        "LANG 10300",
        course("ARTS 10100", core_tags=["arts"]),
        course("ARTS 10200", core_tags=["arts"]),
        "CIVA 20100",
        "FAKE 20000",
        "FAKE 20100",
        "FAKE 20200",
    ]
)
CORE = program(
    "core",
    {
        "group": {
            "all": True,
            "children": [
                {"id": "language", "slot": {"any_of": ["LANG 10300"]}},
                {"id": "arts", "select": {"count": 1, "from": {"tags": ["core:arts"]}}},
            ],
        }
    },
    type="core",
)
MAJOR = program("fake-ba", {"select": {"count": 2, "from": {"subject": "FAKE"}}})


def quarters(courses: list[Any], per_term: int = 4) -> dict[str, list[Any]]:
    return {T[i // per_term]: courses[i : i + per_term] for i in range(0, len(courses), per_term)}


def messages(report: Report) -> str:
    return " | ".join(i.message for i in found(report, "V09", "error"))


def test_4200_units_with_3800_by_enrollment() -> None:
    rules = ruleset(college=college(total_units=4200, units_by_enrollment=3800))
    ap = [{"kind": "AP", "label": f"AP {i}", "units": 100} for i in range(4)]

    def run(p: PlanState) -> Report:
        return verify(p, rules, CAT, V09)

    # 3800 by enrollment + 400 of exam credit = 4200: the totals hold
    ok = run(plan(quarters(FILL[:38]), credits=ap))
    assert "units" not in messages(ok)
    rows = {r.node_id: (r.satisfied, r.have, r.need, r.unit) for r in ok.progress}
    assert rows["college/total_units"] == (True, 4200, 4200, "units")
    assert rows["college/units_by_enrollment"] == (True, 3800, 3800, "units")
    # 4200 in total but only 3700 by enrollment (five transfer courses)
    transfer = [{"course": c, "status": "transfer"} for c in FILL[37:42]]
    short = run(plan({**quarters(FILL[:37]), "2026-SU": transfer}))
    assert "4200 units in total" not in messages(short)
    assert (
        "Graduation needs 3800 units earned by enrollment; this plan has 3700 so far (100 to go)."
        in messages(short)
    )
    # 4100 in total
    less = run(plan(quarters(FILL[:38]), credits=ap[:3]))
    assert (
        "Graduation needs 4200 units in total; this plan has 4100 so far (100 to go)."
        in messages(less)
    )
    issue = next(i for i in less.issues if i.node_id == "college/total_units")
    assert issue.fix_hints == ["Add 100 more units of courses taken at the College."]
    # a partial plan: explicit message, progress still reported
    partial = run(plan(quarters(FILL[:8]) | {T[2]: [{"slot_ref": "x"}]}))
    assert "this plan has 900 so far (3300 to go)" in messages(partial)
    assert {r.node_id: r.have for r in partial.progress}["college/units_by_enrollment"] == 900
    assert partial.status == "errors" and partial.certificate is None


def test_transfer_credit_counts_by_enrollment_and_1800_at_the_college() -> None:
    """Q6 (Richard, 2026-11-14): transfer credit counts toward the 3800 by enrollment, and at
    least 1800 units must be taken at the College."""
    rules = ruleset(
        college=college(
            total_units=4200,
            units_by_enrollment=3800,
            residency_min_units=1800,
            transfer_counts_by_enrollment=True,
        )
    )

    def run(p: PlanState) -> Report:
        return verify(p, rules, CAT, V09)

    # A transfer student: 2400 of transfer credit and 18 courses here.
    transfer = [{"kind": "transfer", "label": "Two years elsewhere", "units": 2400}]
    ok = run(plan(quarters(FILL[:18]), credits=transfer))
    rows = {r.node_id: (r.satisfied, r.have, r.need) for r in ok.progress}
    assert rows["college/units_by_enrollment"] == (True, 4200, 3800)
    assert rows["college/residency_min_units"] == (True, 1800, 1800)
    assert "units" not in messages(ok)
    # 17 courses here: the totals hold, but only 1700 units at the College.
    short = run(plan(quarters(FILL[:17]), credits=[{**transfer[0], "units": 2500}]))
    assert (
        "Graduation needs 1800 units taken at the College; this plan has 1700 so far "
        "(100 to go)." in messages(short)
    )
    # Exam credit never counts by enrollment.
    ap = [{"kind": "AP", "label": "AP", "units": 2400}]
    exam = run(plan(quarters(FILL[:18]), credits=ap))
    assert "3800 units earned by enrollment; this plan has 1800" in messages(exam)
    # Without the flag (the earlier encoding) transfer credit does not count.
    strict = ruleset(college=college(total_units=4200, units_by_enrollment=3800))
    old = verify(plan(quarters(FILL[:18]), credits=transfer), strict, CAT, V09)
    assert "3800 units earned by enrollment" in messages(old)


def test_v09_core_language_and_missing_values() -> None:
    rules = ruleset(CORE, MAJOR, college=college(language_node="core/language"))
    no_core = verify(plan(programs=["fake-ba"]), rules, CAT, V09)
    assert "does not include the Core (core)" in messages(no_core)
    assert found(no_core, "V09")[0].fix_hints == ["Add the program core to the plan."]
    empty = verify(plan(programs=["core"]), rules, CAT, V09)
    assert "The Core is not complete" in messages(empty)
    assert "The Language Competence requirement is not complete." in messages(empty)
    arts_only = verify(plan({T[0]: ["LANG 10300"]}, programs=["core"]), rules, CAT, V09)
    assert "Language Competence" not in messages(arts_only) and "Core is not complete" in messages(
        arts_only
    )
    done = verify(plan({T[0]: ["LANG 10300", "ARTS 10100"]}, programs=["core"]), rules, CAT, V09)
    assert done.status == "valid"
    assert any("total_units" in a for a in done.assumptions)
    assert any("max_quarters" in a for a in done.assumptions)
    assert any("residency share" in a for a in done.assumptions)
    unnamed = ruleset(CORE, college=college())
    report = verify(
        plan({T[0]: ["LANG 10300", "ARTS 10100"]}, programs=["core"]), unnamed, CAT, V09
    )
    assert any("Language Competence" in a for a in report.assumptions)
    # a listed Core without rules is V01's business, not V09's
    assert verify(plan(programs=["core"]), ruleset(college=college()), CAT, V09).status == "valid"
    assert "No College policy" in verify(plan(), ruleset(), CAT, V09).assumptions[0]


def test_v09_half_of_each_program_in_residence() -> None:
    rules = ruleset(CORE, MAJOR, college=college(residency_min_fraction=0.5))
    opts = VerifyOptions(checks=["V03", "V07", "V09"])
    away = {"status": "transfer"}

    def run(items: dict[str, list[Any]]) -> Report:
        p = plan(items, programs=["core", "fake-ba"])
        report = verify(p, rules, CAT, opts)
        if report.certificate is not None:
            assert check_certificate(p, rules, CAT, report.certificate)
        return report

    core = ["LANG 10300", "ARTS 10100"]
    both_away = run(
        {T[0]: [*core, {"course": "FAKE 20000", **away}, {"course": "FAKE 20100", **away}]}
    )
    (issue,) = found(both_away, "V09", "error")
    assert issue.node_id == "fake-ba" and "in residence" in issue.message
    half = run({T[0]: [*core, {"course": "FAKE 20000", **away}, "FAKE 20100"]})
    assert half.status == "valid"
    # the solver prefers an assignment that keeps the residency share
    pick = run(
        {
            T[0]: [
                *core,
                {"course": "FAKE 20000", **away},
                {"course": "FAKE 20100", **away},
                "FAKE 20200",
            ]
        }
    )
    assert pick.status == "valid"
    used = next(a.courses for a in pick.certificate.assignments if a.node == "fake-ba")  # type: ignore[union-attr]
    assert "FAKE 20200" in used
    # the Core is exempt from the College share (exam credit may cover it) ...
    credit_core = plan(
        {T[0]: ["FAKE 20000", "FAKE 20100"]},
        programs=["core", "fake-ba"],
        credits=[{"kind": "AP", "label": "a", "maps_to": c} for c in core],
    )
    assert verify(credit_core, rules, CAT, opts).status == "valid"
    # ... unless a program states its own share
    own = program("fake-ba", MAJOR.rules.model_dump(), policy={"residency": {"min_fraction": 1.0}})
    strict = verify(
        plan(
            {T[0]: [*core, {"course": "FAKE 20000", **away}, "FAKE 20100"]},
            programs=["core", "fake-ba"],
        ),
        ruleset(CORE, own, college=college()),
        CAT,
        opts,
    )
    assert [i.node_id for i in found(strict, "V09", "error")] == ["fake-ba"]


def test_v09_quarters_within_the_allotment() -> None:
    rules = ruleset(college=college(max_quarters=3))
    p = plan(
        {T[0]: FILL[:1], T[1]: FILL[1:2], "2027-SU": FILL[2:3], T[2]: FILL[3:4], T[3]: FILL[4:5]}
    )
    issue = found(verify(p, rules, CAT, V09), "V09", "error")[-1]
    assert "uses 4 quarters; the College allows 3" in issue.message and issue.term_ids == [T[3]]
    few = verify(plan({T[0]: FILL[:1], "2027-SU": FILL[2:3]}), rules, CAT, V09)
    assert "quarters" not in messages(few)


# ----------------------------------------------------------------------------------- V10


def test_v10_core_by_the_end_of_second_year() -> None:
    rules = ruleset(CORE, college=college(core_complete_by="Y2-SP", civ_abroad_year=3))
    on_time = plan({T[0]: ["LANG 10300"], T[5]: ["ARTS 10100"]}, programs=["core"])
    assert not verify(on_time, rules, CAT, V10).issues
    late = plan({T[0]: ["LANG 10300"], T[6]: ["ARTS 10100"]}, programs=["core"])
    (issue,) = verify(late, rules, CAT, V10).issues
    assert (issue.code, issue.level, issue.node_id) == ("V10", "warning", "core")
    assert issue.message == "core should be finished by 2028-SP, but ARTS 10100 come later."
    assert issue.fix_hints == ["Move ARTS 10100 to 2028-SP or earlier."]
    # a late arts course does not matter when an on-time one exists, whatever the solver picked
    spare = plan({T[0]: ["LANG 10300", "ARTS 10200"], T[6]: ["ARTS 10100"]}, programs=["core"])
    assert not verify(spare, rules, CAT, V10).issues
    # incomplete Core
    partial = plan({T[0]: ["LANG 10300"]}, programs=["core"])
    (issue,) = verify(partial, rules, CAT, V10).issues
    assert "it is not complete in this plan" in issue.message
    assert issue.fix_hints == ["Plan the remaining core requirements by 2028-SP."]
    # credits are always on time; no deadline encoded -> nothing to check
    credit = plan(
        {T[0]: ["LANG 10300"]},
        programs=["core"],
        credits=[{"kind": "AP", "label": "a", "maps_to": "ARTS 10100"}],
    )
    assert not verify(credit, rules, CAT, V10).issues
    assert not verify(late, ruleset(CORE, college=college()), CAT, V10).issues
    assert not verify(plan(), rules, CAT, V10).issues


def test_v10_civilization_abroad_is_allowed_in_third_year() -> None:
    core = program(
        "core",
        {
            "group": {
                "all": True,
                "children": [
                    {"id": "language", "slot": {"any_of": ["LANG 10300"]}},
                    {"id": "civ", "select": {"count": 1, "from": {"subject": "CIVA"}}},
                ],
            }
        },
        type="core",
    )
    block = program("paris-civ", {"slot": {"any_of": ["CIVA 20100"]}}, type="study_abroad_block")
    rules = ruleset(core, block, college=college(core_complete_by="Y2-SP", civ_abroad_year=3))
    items = {T[0]: ["LANG 10300"], T[7]: ["CIVA 20100"]}
    plain = verify(plan(items, programs=["core"]), rules, CAT, V10)
    assert [i.course_ids for i in plain.issues] == [["CIVA 20100"]]
    # as part of a study-abroad block of the plan, third year is fine
    assert not verify(plan(items, programs=["core", "paris-civ"]), rules, CAT, V10).issues
    # or when a study-abroad goal names that term
    goal = {"id": "g1", "type": "study_abroad", "program_id": "paris-civ", "abroad_term": "Y3-WI"}
    assert not verify(plan(items, programs=["core"], goals=[goal]), rules, CAT, V10).issues
    # fourth year is too late either way
    fourth = {T[0]: ["LANG 10300"], T[10]: ["CIVA 20100"]}
    assert verify(plan(fourth, programs=["core", "paris-civ"]), rules, CAT, V10).issues


def test_v10_program_apply_by_and_complete_by() -> None:
    bxms = program(
        "fake-bxms",
        {"select": {"count": 2, "from": {"subject": "FAKE"}}},
        type="bxms",
        policy={
            "timing": {
                "apply_by": "Y3-WI",
                "complete_by": "Y3-SP",
                "apply_requires": ["FAKE 20000", "FAKE 20200"],
            }
        },
    )
    rules = ruleset(bxms)
    good = plan({T[5]: ["FAKE 20000"], T[6]: ["FAKE 20200"]}, programs=["fake-bxms"])
    assert not verify(good, rules, CAT, V10).issues
    late = plan(
        {T[5]: ["FAKE 20000"], T[7]: ["FAKE 20200"], T[9]: ["FAKE 20100"]}, programs=["fake-bxms"]
    )
    report = verify(late, rules, CAT, V10)
    assert [i.message for i in report.issues] == [
        "fake-bxms: FAKE 20200 must be complete before the application deadline 2029-WI."
    ]
    too_late = plan({T[5]: ["FAKE 20000"], T[9]: ["FAKE 20200"]}, programs=["fake-bxms"])
    report = verify(too_late, rules, CAT, V10)
    assert len(report.issues) == 2 and report.status == "warnings"
    assert "should be finished by 2029-SP, but FAKE 20200 come later" in report.issues[1].message
    assert error_codes(report) == set()
