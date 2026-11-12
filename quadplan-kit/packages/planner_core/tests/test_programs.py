"""V07, V08 and V12: node semantics of the CP-SAT model, sharing between programs."""

from typing import Any

from core_support import T, catalog, course, error_codes, found, plan, program, ruleset
from planner_core import check_certificate, verify
from planner_core.models import Catalog, PlanState, Report, RuleSet, VerifyOptions

OPTS = VerifyOptions(checks=["V01", "V02", "V03", "V07", "V08", "V12"])


def run(p: PlanState, rules: RuleSet, cat: Catalog) -> Report:
    report = verify(p, rules, cat, OPTS)
    if report.certificate is not None:
        assert check_certificate(p, rules, cat, report.certificate)
    else:
        assert report.status == "errors"
    return report


def assigned(report: Report) -> dict[str, list[str]]:
    assert report.certificate is not None
    return {a.node: a.courses for a in report.certificate.assignments}


def progress(report: Report) -> dict[str, tuple[bool, int, int]]:
    return {p.node_id: (p.satisfied, p.have, p.need) for p in report.progress}


# ------------------------------------------------------------------- the Core HCA example

HUMA_A = ["HUMA 11000", "HUMA 11100", "HUMA 11200"]
HUMA_B = ["HUMA 12000", "HUMA 12100", "HUMA 12200"]
CIV_A = ["CIVA 20100", "CIVA 20200", "CIVA 20300"]
CIV_B = ["CIVB 20100", "CIVB 20200", "CIVB 20300"]
ARTS = ["ARTS 10100", "ARTS 10200", "ARTS 10300"]
HCA_CATALOG = catalog(
    [*HUMA_A, *HUMA_B, *CIV_A, *CIV_B, *[course(c, core_tags=["arts"]) for c in ARTS]],
    course_lists=[
        {"name": "core-huma-sequences", "sublists": ["huma-a", "huma-b"]},
        {"name": "huma-a", "courses": HUMA_A},
        {"name": "huma-b", "courses": HUMA_B},
        {"name": "core-civ-sequences", "sublists": ["civ-a", "civ-b"]},
        {"name": "civ-a", "courses": CIV_A},
        {"name": "civ-b", "courses": CIV_B},
    ],
)
HCA = program(
    "core",
    {
        "id": "core-hca",
        "label": "Humanities, Civilization Studies, and the Arts",
        "bounded_parts": {
            "total": {"courses": 6},
            "parts": [
                {
                    "id": "huma",
                    "from": {"list": "core-huma-sequences"},
                    "count": [2, 3],
                    "same_sequence": True,
                },
                {
                    "id": "civ",
                    "from": {"list": "core-civ-sequences"},
                    "count": [2, 3],
                    "same_sequence": True,
                },
                {"id": "arts", "from": {"tags": ["core:arts"]}, "count": [1, 2]},
            ],
        },
        "constraints": {"no_pass_fail": True},
    },
    type="core",
)


def hca_plan(*courses: Any) -> PlanState:
    return (
        plan({T[i % 6]: [c] for i, c in enumerate(courses)}, programs=["core"])
        if len(courses) <= 6
        else plan({T[0]: list(courses)}, programs=["core"])
    )


def test_bounded_parts_2_3_2_3_1_2_summing_to_6_satisfiable() -> None:
    rules = ruleset(HCA)
    for courses in (
        [*HUMA_A, *CIV_A[:2], ARTS[0]],  # 3 + 2 + 1
        [*HUMA_B[:2], *CIV_B, ARTS[1]],  # 2 + 3 + 1
        [*HUMA_A[:2], *CIV_A[:2], *ARTS[:2]],  # 2 + 2 + 2
    ):
        report = run(hca_plan(*courses), rules, HCA_CATALOG)
        assert report.status == "valid", report.issues
        used = assigned(report)
        assert sum(len(v) for v in used.values()) == 6
        assert progress(report)["core"] == (True, 6, 6)
    # seven eligible courses: exactly six are used
    report = run(hca_plan(*HUMA_A, *CIV_A, ARTS[0]), rules, HCA_CATALOG)
    assert report.status == "valid" and sum(len(v) for v in assigned(report).values()) == 6


def test_bounded_parts_not_satisfiable() -> None:
    rules = ruleset(HCA)
    # 2 + 2 + 1 = 5: every part is within bounds but the total is short
    report = run(hca_plan(*HUMA_A[:2], *CIV_A[:2], ARTS[0]), rules, HCA_CATALOG)
    (issue,) = found(report, "V07", "error")
    assert issue.node_id == "core"
    assert (
        "needs 6 courses in total, has 5 (huma 2 of 2-3; civ 2 of 2-3; arts 1 of 1-2)"
        in issue.message
    )
    assert issue.fix_hints == ["Add courses to reach 6 courses across the parts."]
    assert progress(report)["core"] == (False, 5, 6)
    assert progress(report)["core/huma"] == (True, 2, 2)
    # 3 + 3 + 0: the arts minimum is missing
    report = run(hca_plan(*HUMA_A, *CIV_A), rules, HCA_CATALOG)
    hint = found(report, "V07", "error")[0].fix_hints[0]
    assert hint.startswith("Add 1 more for arts: tagged core:arts")
    assert progress(report)["core/arts"] == (False, 0, 1)
    # three arts courses cannot stand in for a humanities course (max 2)
    report = run(hca_plan(*HUMA_A[:1], *CIV_A[:2], *ARTS), rules, HCA_CATALOG)
    assert error_codes(report) == {"V07"}
    assert progress(report)["core/arts"][1] == 2


def test_same_sequence() -> None:
    rules = ruleset(HCA)
    # humanities from two different sequences: only one sequence counts
    mixed = hca_plan(HUMA_A[0], HUMA_B[0], *CIV_A[:2], *ARTS[:2])
    report = run(mixed, rules, HCA_CATALOG)
    (issue,) = found(report, "V07", "error")
    assert "huma 1 of 2-3" in issue.message
    assert "all from one sequence" in issue.fix_hints[0]
    # two full humanities sequences are fine: one is picked
    both = hca_plan(*HUMA_A, *HUMA_B, *CIV_A[:2], ARTS[0])
    report = run(both, rules, HCA_CATALOG)
    assert report.status == "valid"
    huma = assigned(report)["core/huma"]
    assert set(huma) <= set(HUMA_A) or set(huma) <= set(HUMA_B)
    # a tampered certificate that mixes sequences is rejected
    cert = report.certificate.model_copy(deep=True)  # type: ignore[union-attr]
    for a in cert.assignments:
        if a.node == "core/huma":
            a.courses = [HUMA_A[0], HUMA_B[1], *a.courses[2:]]
    assert not check_certificate(both, rules, HCA_CATALOG, cert)


def test_same_sequence_without_sequences_cannot_be_satisfied() -> None:
    flat = program(
        "p",
        {
            "select": {"count": 2, "from": {"subject": "HUMA"}},
            "constraints": {"same_sequence": True},
        },
    )
    report = run(plan({T[0]: HUMA_A[:2]}, programs=["p"]), ruleset(flat), HCA_CATALOG)
    assert error_codes(report) == {"V07"}


def test_v12_pass_fail_where_the_node_forbids_it() -> None:
    rules = ruleset(HCA)
    courses = [*HUMA_A, *CIV_A[:2], {"course": ARTS[0], "grading": "pass_fail"}]
    report = run(hca_plan(*courses), rules, HCA_CATALOG)
    assert error_codes(report) == {"V07", "V12"}
    (issue,) = found(report, "V12")
    assert issue.course_ids == [ARTS[0]] and issue.node_id == "core/arts"
    assert issue.fix_hints == ["Take ARTS 10100 for a letter grade."]
    assert found(report, "V07")[0].course_ids == [ARTS[0]]
    # with another arts course for a letter grade, the Pass/Fail one is just a free elective
    report = run(hca_plan(*courses, ARTS[1]), rules, HCA_CATALOG)
    assert report.status == "valid" and assigned(report)["core/arts"] == [ARTS[1]]
    # a certificate that uses the Pass/Fail course is rejected
    p = hca_plan(*courses, ARTS[1])
    cert = report.certificate.model_copy(deep=True)  # type: ignore[union-attr]
    next(a for a in cert.assignments if a.node == "core/arts").courses = [ARTS[0]]
    assert not check_certificate(p, rules, HCA_CATALOG, cert)


# ------------------------------------------------------------------- slots, selects, groups

FAKES = [f"FAKE {n}" for n in range(20000, 21000, 100)]  # FAKE 20000 .. FAKE 20900
BASE = catalog(
    [
        "FAKE 10000",
        "FAKE 10100",
        *FAKES,
        "FKE 30000",
        course("BIGG 20000", units=200),
        course("HALF 20000", units=50),
        "MATH 20000",
        "STAT 20000",
    ],
    crosslist_groups=[["FAKE 20000", "FKE 30000"]],
)
MAJOR = program(
    "fake-bs",
    {
        "group": {
            "all": True,
            "children": [
                {
                    "id": "intro",
                    "group": {
                        "all": True,
                        "children": [
                            {"slot": {"any_of": ["FAKE 10000"]}},
                            {"slot": {"any_of": ["FAKE 10100", "FAKE 20900"]}},
                        ],
                    },
                },
                {
                    "id": "electives",
                    "label": "Electives",
                    "select": {
                        "count": 2,
                        "from": {
                            "subject": "FAKE",
                            "number_range": [20000, 29999],
                            "exclude": ["FAKE 20900"],
                        },
                    },
                },
            ],
        }
    },
)


def test_slot_select_group_and_cross_listed_code() -> None:
    rules = ruleset(MAJOR)
    p = plan(
        {T[0]: ["FAKE 10000", "FAKE 10100"], T[1]: ["FKE 30000", "FAKE 20100", "FAKE 20200"]},
        programs=["fake-bs"],
    )
    report = run(p, rules, BASE)
    assert report.status == "valid"
    used = assigned(report)
    assert used["fake-bs/intro/1"] == ["FAKE 10000"] and used["fake-bs/intro/2"] == ["FAKE 10100"]
    assert len(used["fake-bs/electives"]) == 2  # third eligible course stays a free elective
    # the cross-listed code FKE 30000 matches the FAKE selector through its partner
    p = plan(
        {T[0]: ["FAKE 10000", "FAKE 10100"], T[1]: ["FKE 30000", "FAKE 20100"]},
        programs=["fake-bs"],
    )
    assert assigned(run(p, rules, BASE))["fake-bs/electives"] == ["FAKE 20100", "FKE 30000"]
    assert progress(run(p, rules, BASE))["fake-bs"] == (True, 2, 2)


def test_v07_lists_exactly_what_is_missing() -> None:
    rules = ruleset(MAJOR)
    p = plan({T[0]: ["FAKE 10000"], T[1]: ["FAKE 20100", "FAKE 20900"]}, programs=["fake-bs"])
    report = run(p, rules, BASE)
    issues = found(report, "V07", "error")
    # FAKE 20900 fills the second intro slot (it is excluded from electives)
    assert [i.node_id for i in issues] == ["fake-bs/electives"]
    assert issues[0].message == (
        "Electives: 1 of 2 courses; 1 more needed from FAKE 20000-29999, except FAKE 20900."
    )
    assert progress(report)["fake-bs/electives"] == (False, 1, 2)
    assert progress(report)["fake-bs/intro"] == (True, 2, 2)
    empty = run(plan(programs=["fake-bs"]), rules, BASE)
    assert [i.node_id for i in found(empty, "V07")] == [
        "fake-bs/intro/1",
        "fake-bs/intro/2",
        "fake-bs/electives",
    ]
    assert found(empty, "V07")[1].fix_hints == ["Add FAKE 10100 or FAKE 20900."]
    assert progress(empty)["fake-bs"] == (False, 0, 2)


def test_a_course_fills_one_node_unless_double_counting_is_allowed() -> None:
    def rules(double: bool) -> RuleSet:
        return ruleset(
            program(
                "p",
                {
                    "group": {
                        "all": True,
                        "children": [
                            {"id": "a", "slot": {"any_of": ["FAKE 20000"]}},
                            {
                                "id": "b",
                                "select": {"count": 1, "from": {"subject": "FAKE"}},
                                "constraints": {"allow_double_count": double},
                            },
                        ],
                    }
                },
            )
        )

    p = plan({T[0]: ["FAKE 20000"]}, programs=["p"])
    strict = run(p, rules(False), BASE)
    assert [i.node_id for i in found(strict, "V07")] == ["p/b"]
    loose = run(p, rules(True), BASE)
    assert loose.status == "valid" and assigned(loose) == {
        "p/a": ["FAKE 20000"],
        "p/b": ["FAKE 20000"],
    }
    # the same certificate is rejected under the rule without double counting
    cert = loose.certificate.model_copy(
        update={"rules": strict.certificate.rules if strict.certificate else {}}
    )  # type: ignore[union-attr]
    assert not check_certificate(p, rules(False), BASE, cert)


def test_select_by_units() -> None:
    rules = ruleset(
        program("p", {"select": {"units": 300, "from": {"number_range": [20000, 29999]}}})
    )
    short = run(plan({T[0]: ["BIGG 20000", "HALF 20000"]}, programs=["p"]), rules, BASE)
    (issue,) = found(short, "V07")
    assert "250 of 300 units; 50 more needed" in issue.message
    assert progress(short)["p"] == (False, 250, 300)
    ok = run(plan({T[0]: ["BIGG 20000", "FAKE 20100", "FAKE 20200"]}, programs=["p"]), rules, BASE)
    used = assigned(ok)["p"]
    assert ok.status == "valid" and len(used) == 2 and "BIGG 20000" in used  # fewest courses
    override = plan({T[0]: [{"course": "FAKE 20100", "units": 300}]}, programs=["p"])
    assert run(override, rules, BASE).status == "valid"


def test_group_n_of_picks_the_options_closest_to_done() -> None:
    def track(pid: str, codes: list[str]) -> dict[str, Any]:
        children = [{"slot": {"any_of": [c]}} for c in codes]
        return {"id": pid, "label": f"Track {pid}", "group": {"all": True, "children": children}}

    rules = ruleset(
        program(
            "p",
            {
                "group": {
                    "n_of": 2,
                    "children": [
                        track("a", FAKES[0:2]),
                        track("b", FAKES[2:4]),
                        track("c", FAKES[4:6]),
                    ],
                }
            },
        )
    )
    done = run(plan({T[0]: FAKES[0:4]}, programs=["p"]), rules, BASE)
    assert done.status == "valid" and progress(done)["p"] == (True, 2, 2)
    # all three complete: only two are used
    three = run(plan({T[0]: FAKES[0:6]}, programs=["p"]), rules, BASE)
    assert three.status == "valid" and sum(len(v) for v in assigned(three).values()) == 4
    part = run(plan({T[0]: [*FAKES[0:2], FAKES[4]]}, programs=["p"]), rules, BASE)
    (issue,) = found(part, "V07")
    assert issue.node_id == "p" and "1 of 2 required parts are complete" in issue.message
    assert issue.fix_hints == ["Complete Track b.", "Complete Track c."]
    assert progress(part)["p/c/1"] == (True, 1, 1) and progress(part)["p/c"] == (False, 1, 2)


def test_program_satisfaction_beats_satisfying_more_sub_nodes() -> None:
    """One course fits either a required slot or a big optional track: the root must win."""
    big = {
        "id": "big",
        "group": {"all": True, "children": [{"slot": {"any_of": [c]}} for c in FAKES[0:5]]},
    }
    rules = ruleset(
        program(
            "p",
            {
                "group": {
                    "all": True,
                    "children": [
                        {"id": "need", "slot": {"any_of": ["FAKE 20000"]}},
                        {
                            "id": "pick",
                            "group": {
                                "n_of": 1,
                                "children": [
                                    big,
                                    {"id": "small", "slot": {"any_of": ["FAKE 20900"]}},
                                ],
                            },
                        },
                    ],
                }
            },
        )
    )
    report = run(plan({T[0]: [*FAKES[0:4], "FAKE 20900"]}, programs=["p"]), rules, BASE)
    assert report.status == "valid"
    assert assigned(report) == {"p/need": ["FAKE 20000"], "p/pick/small": ["FAKE 20900"]}


def test_max_from_and_distinct_subjects() -> None:
    outside = {"union": [{"subject": "MATH"}, {"subject": "STAT"}]}
    rules = ruleset(
        program(
            "p",
            {
                "select": {"count": 3, "from": {"number_range": [20000, 20999]}},
                "constraints": {"max_from": {"selector": outside, "n": 1}, "distinct_subjects": 2},
            },
        )
    )
    two_outside = plan({T[0]: ["FAKE 20100", "MATH 20000", "STAT 20000"]}, programs=["p"])
    report = run(two_outside, rules, BASE)
    assert "at most 1 from (any MATH course; or any STAT course)" in found(report, "V07")[0].message
    one_subject = plan({T[0]: ["FAKE 20100", "FAKE 20200", "FAKE 20300"]}, programs=["p"])
    assert "from at least 2 subjects" in found(run(one_subject, rules, BASE), "V07")[0].message
    good = plan({T[0]: ["FAKE 20100", "FAKE 20200", "FAKE 20300", "MATH 20000"]}, programs=["p"])
    report = run(good, rules, BASE)
    assert report.status == "valid" and "MATH 20000" in assigned(report)["p"]
    # a certificate that breaks either constraint is rejected
    for courses in (["FAKE 20100", "FAKE 20200", "FAKE 20300"],):
        cert = report.certificate.model_copy(deep=True)  # type: ignore[union-attr]
        cert.assignments[0].courses = courses
        assert not check_certificate(good, rules, BASE, cert)
    wide = plan({T[0]: ["FAKE 20100", "MATH 20000", "STAT 20000", "FAKE 20200"]}, programs=["p"])
    cert = run(wide, rules, BASE).certificate.model_copy(deep=True)  # type: ignore[union-attr]
    cert.assignments[0].courses = ["FAKE 20100", "MATH 20000", "STAT 20000"]
    assert not check_certificate(wide, rules, BASE, cert)


def test_group_level_constraints_apply_to_the_whole_subtree() -> None:
    rules = ruleset(
        program(
            "p",
            {
                "group": {
                    "all": True,
                    "children": [
                        {
                            "id": "a",
                            "select": {"count": 1, "from": {"number_range": [20000, 20999]}},
                        },
                        {
                            "id": "b",
                            "select": {"count": 1, "from": {"number_range": [20000, 20999]}},
                        },
                    ],
                },
                "constraints": {"distinct_subjects": 2, "no_pass_fail": True, "min_grade": "C"},
            },
        )
    )
    same = run(plan({T[0]: ["FAKE 20100", "FAKE 20200"]}, programs=["p"]), rules, BASE)
    (issue,) = found(same, "V07")
    assert (
        issue.node_id == "p" and "do not meet the rule (from at least 2 subjects)" in issue.message
    )
    mixed = run(plan({T[0]: ["FAKE 20100", "MATH 20000"]}, programs=["p"]), rules, BASE)
    assert mixed.status == "valid"
    assert mixed.assumptions == [
        "Courses without a recorded grade are assumed to meet grade minimums."
    ]
    low = plan(
        {T[0]: ["FAKE 20100", {"course": "MATH 20000", "status": "completed", "grade": "D+"}]},
        programs=["p"],
    )
    report = run(low, rules, BASE)
    hints = [h for i in found(report, "V07") for h in i.fix_hints]
    assert "MATH 20000 has grade D+, below the minimum C, so it does not count here." in hints
    good = plan(
        {T[0]: ["FAKE 20100", {"course": "MATH 20000", "status": "completed", "grade": "C+"}]},
        programs=["p"],
    )
    assert run(good, rules, BASE).status == "valid"


def test_in_order() -> None:
    rules = ruleset(
        program(
            "p",
            {
                "select": {"count": 2, "from": {"subject": "FAKE"}},
                "constraints": {"in_order": True},
            },
        )
    )
    forward = run(plan({T[0]: ["FAKE 20000"], T[1]: ["FAKE 20100"]}, programs=["p"]), rules, BASE)
    assert forward.status == "valid"
    backward = plan({T[1]: ["FAKE 20000"], T[0]: ["FAKE 20100"]}, programs=["p"])
    report = run(backward, rules, BASE)
    assert "taken in order" in found(report, "V07")[0].message
    same_term = run(plan({T[0]: ["FAKE 20000", "FAKE 20100"]}, programs=["p"]), rules, BASE)
    assert error_codes(same_term) == {"V07"}
    credit = plan(
        {T[0]: ["FAKE 20100"]},
        programs=["p"],
        credits=[{"kind": "AP", "label": "x", "maps_to": "FAKE 20000"}],
    )
    assert run(credit, rules, BASE).status == "valid"
    cert = forward.certificate.model_copy(
        update={"plan_hash": verify(backward, rules, BASE).plan_hash}
    )  # type: ignore[union-attr]
    assert not check_certificate(backward, rules, BASE, cert)


# ------------------------------------------------------------------- V08 sharing


def two(pid: str, **fields: Any) -> Any:
    return program(
        pid,
        {"select": {"count": 2, "from": {"subject": "FAKE", "number_range": [20000, 20999]}}},
        **fields,
    )


def test_v08_minor_sharing_with_a_major() -> None:
    major = two("fake-ba")
    minor = two("fake-minor", type="minor", policy={"share": [{"with": "type:major", "max": 0}]})
    rules = ruleset(major, minor)
    three = plan({T[0]: FAKES[0:3]}, programs=["fake-ba", "fake-minor"])
    report = run(three, rules, BASE)
    assert error_codes(report) == {"V07", "V08"}
    (v08,) = found(report, "V08")
    assert "fake-minor may share at most 0 course(s) with fake-ba" in v08.message
    assert len(v08.course_ids) == 1 and v08.node_id == "fake-minor"
    (v07,) = found(report, "V07")
    assert v07.node_id == "fake-minor" and "beyond the sharing limit (see V08)" in v07.message
    rows = progress(report)
    assert rows["fake-ba"][0] is True and rows["fake-minor"][0] is False
    assert report.certificate is None
    four = plan({T[0]: FAKES[0:4]}, programs=["fake-ba", "fake-minor"])
    report = run(four, rules, BASE)
    assert report.status == "valid"
    used = assigned(report)
    assert not set(used["fake-ba"]) & set(used["fake-minor"])
    # a certificate in which both programs count the same courses is rejected
    cert = report.certificate.model_copy(deep=True)  # type: ignore[union-attr]
    cert.assignments[1].courses = list(cert.assignments[0].courses)
    assert not check_certificate(four, rules, BASE, cert)
    # with a limit of one, three courses are enough
    minor1 = two("fake-minor", type="minor", policy={"share": [{"with": "type:major", "max": 1}]})
    assert run(three, ruleset(major, minor1), BASE).status == "valid"
    # two majors without a limit may share everything
    assert (
        run(
            plan({T[0]: FAKES[0:2]}, programs=["fake-ba", "other-ba"]),
            ruleset(major, two("other-ba")),
            BASE,
        ).status
        == "valid"
    )


def test_v08_minor_sharing_with_the_core_except_language() -> None:
    cat = catalog(["LANG 10300", course("ARTS 10100", core_tags=["arts"]), "FAKE 20000"])
    core = program(
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

    def minor(codes: list[str]) -> Any:
        return program(
            "fake-minor",
            {"select": {"count": 2, "from": {"codes": codes}}},
            type="minor",
            policy={"share": [{"with": "core", "max": 0, "except": ["language"]}]},
        )

    p = plan({T[0]: ["LANG 10300", "ARTS 10100", "FAKE 20000"]}, programs=["core", "fake-minor"])
    # sharing the language course is allowed by `except`
    ok = run(p, ruleset(core, minor(["LANG 10300", "FAKE 20000"])), cat)
    assert ok.status == "valid" and assigned(ok)["fake-minor"] == ["FAKE 20000", "LANG 10300"]
    # sharing the arts course is not
    bad = run(p, ruleset(core, minor(["ARTS 10100", "FAKE 20000"])), cat)
    assert error_codes(bad) == {"V07", "V08"}
    assert found(bad, "V08")[0].course_ids == ["ARTS 10100"]


def test_v08_bxms_share_limit_and_required_major() -> None:
    major = two("fake-bs")
    bxms = program(
        "fake-bxms",
        {"select": {"count": 3, "from": {"subject": "FAKE", "number_range": [20000, 20999]}}},
        type="bxms",
        policy={
            "share": [{"with": "program:fake-bs", "max": 1}],
            "requires": ["fake-b?"],
            "excludes": ["fake-minor"],
        },
    )
    rules = ruleset(major, bxms, two("fake-minor", type="minor"))
    both = ["fake-bs", "fake-bxms"]
    ok = run(plan({T[0]: FAKES[0:4]}, programs=both), rules, BASE)
    assert ok.status == "valid"
    used = assigned(ok)
    assert len(set(used["fake-bs"]) & set(used["fake-bxms"])) == 1
    short = run(plan({T[0]: FAKES[0:3]}, programs=both), rules, BASE)
    assert error_codes(short) == {"V07", "V08"}
    assert (
        "may share at most 1 course(s) with fake-bs, but 2 count toward both"
        in found(short, "V08")[0].message
    )
    alone = run(plan({T[0]: FAKES[0:3]}, programs=["fake-bxms"]), rules, BASE)
    assert "fake-bxms requires the program fake-b?" in found(alone, "V08")[0].message
    clash = run(plan({T[0]: FAKES[0:6]}, programs=[*both, "fake-minor"]), rules, BASE)
    assert "fake-bxms cannot be combined with fake-minor." in [
        i.message for i in found(clash, "V08")
    ]


def test_programs_not_in_the_plan_are_ignored_and_plans_without_programs_certify() -> None:
    rules = ruleset(MAJOR)
    p = plan({T[0]: ["FAKE 10000"]})
    report = run(p, rules, BASE)
    assert report.status == "valid" and report.certificate is not None
    assert report.certificate.rules == {} and not report.progress


def test_solver_time_limit_is_reported_not_guessed(monkeypatch: Any) -> None:
    from ortools.sat.python import cp_model
    from planner_core import programs as programs_module
    from planner_core import solver

    p = plan({T[0]: FAKES[0:2]}, programs=["fake-ba"])
    monkeypatch.setattr(solver.cp_model.CpSolver, "solve", lambda self, model: cp_model.UNKNOWN)
    report = verify(p, ruleset(two("fake-ba")), BASE, OPTS)
    assert "could not be checked within the time limit" in found(report, "V07", "error")[0].message
    assert report.certificate is None
    monkeypatch.undo()
    real = solver.solve

    def feasible(*args: Any, **kwargs: Any) -> Any:
        out = real(*args, **kwargs)
        out.status = "feasible"
        return out

    monkeypatch.setattr(programs_module, "solve", feasible)
    report = verify(p, ruleset(two("fake-ba")), BASE, OPTS)
    assert report.status == "valid" and "work limit" in report.assumptions[0]
