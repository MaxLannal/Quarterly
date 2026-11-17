"""V01-V06 on tiny fake fixtures: one edge case per test."""

from core_support import (
    T,
    catalog,
    college,
    course,
    error_codes,
    found,
    plan,
    program,
    ruleset,
    warning_codes,
)
from planner_core import check_certificate, verify
from planner_core.models import Requisite, VerifyOptions

AU1, WI1, SP1 = T[0], T[1], T[2]
SLOT = {"slot": {"any_of": ["FAKE 10000"]}}


def only(*codes: str) -> VerifyOptions:
    return VerifyOptions(checks=list(codes))  # type: ignore[arg-type]


# ----------------------------------------------------------------------------------- V01


def test_v01_unknown_course_credit_program_placeholder_and_year() -> None:
    cat = catalog(["FAKE 10000"])
    rules = ruleset(program("fake-ba", SLOT))
    p = plan(
        {AU1: ["FAKE 10000", "GONE 10000", {"slot_ref": "fake-ba/nope"}], WI1: ["GONE 10000"]},
        programs=["fake-ba", "missing-ba"],
        credits=[{"kind": "AP", "label": "AP Nothing", "maps_to": "GONE 20000", "units": 100}],
    )
    report = verify(p, rules, cat, only("V01"))
    messages = [i.message for i in found(report, "V01", "error")]
    assert len(messages) == 4
    assert any("GONE 10000 is not in the 2026-27 catalog" in m for m in messages)
    assert any("GONE 20000" in m for m in messages)
    assert any("missing-ba has no rules" in m for m in messages)
    assert any("fake-ba/nope" in m for m in messages)
    unknown = next(i for i in report.issues if i.course_ids == ["GONE 10000"])
    assert unknown.term_ids == [AU1, WI1] and unknown.fix_hints
    assert report.status == "errors" and report.certificate is None

    other_year = cat.model_copy(update={"catalog_year": "2025-26"})
    report = verify(plan({AU1: ["FAKE 10000"]}), ruleset(), other_year, only("V01"))
    assert "the catalog are for 2025-26" in found(report, "V01")[0].message


def test_v01_valid_placeholder_is_accepted_but_leaves_the_node_unmet() -> None:
    rules = ruleset(program("fake-ba", SLOT))
    p = plan({AU1: [{"slot_ref": "fake-ba"}]}, programs=["fake-ba"])
    report = verify(p, rules, catalog(["FAKE 10000"]), only("V01", "V03", "V07"))
    assert error_codes(report) == {"V07"}
    assert "Replace the placeholder in 2026-AU with a course." in found(report, "V07")[0].fix_hints


# ----------------------------------------------------------------------------------- V02


def test_v02_cross_listed_duplicate_collapses_to_one_course() -> None:
    cat = catalog(["FAKE 20000", "FKE 30000"], crosslist_groups=[["FAKE 20000", "FKE 30000"]])
    report = verify(plan({AU1: ["FAKE 20000"], WI1: ["FKE 30000"]}), ruleset(), cat, only("V02"))
    (issue,) = found(report, "V02", "error")
    assert "cross-listed" in issue.message
    assert issue.course_ids == ["FAKE 20000", "FKE 30000"] and issue.term_ids == [AU1, WI1]
    # one of them alone is fine, under either code
    for code in ("FAKE 20000", "FKE 30000"):
        assert not verify(plan({AU1: [code]}), ruleset(), cat, only("V02")).issues


def test_v02_plain_duplicate_unless_repeatable() -> None:
    cat = catalog(["FAKE 10000", course("FAKE 29900", repeatable=True)])
    p = plan({AU1: ["FAKE 10000", "FAKE 29900"], WI1: ["FAKE 10000", "FAKE 29900"]})
    (issue,) = verify(p, ruleset(), cat, only("V02")).issues
    assert issue.course_ids == ["FAKE 10000"] and "more than once" in issue.message


def test_v02_mutually_exclusive_pair() -> None:
    cat = catalog(
        ["FAKE 10000", "FAKE 10500", "FAKE 20000"],
        relations=[
            {"a": "FAKE 10000", "b": "FAKE 10500", "kind": "mutually_exclusive"},
            {"a": "FAKE 10500", "b": "FAKE 10000", "kind": "mutually_exclusive"},
        ],
    )
    report = verify(plan({AU1: ["FAKE 10000"], WI1: ["FAKE 10500"]}), ruleset(), cat, only("V02"))
    (issue,) = found(report, "V02", "error")
    assert "mutually exclusive" in issue.message
    assert issue.course_ids == ["FAKE 10000", "FAKE 10500"]
    assert not verify(plan({AU1: ["FAKE 10000", "FAKE 20000"]}), ruleset(), cat, only("V02")).issues


def test_v02_exam_credit_is_forfeited_when_the_course_or_its_equivalent_is_taken() -> None:
    cat = catalog(
        ["FAKE 10000", "FAKE 16000", "FAKE 17000"],
        relations=[
            {"a": "FAKE 10000", "b": "FAKE 16000", "kind": "equivalent"},
            {"a": "FAKE 16000", "b": "FAKE 17000", "kind": "replaces"},
        ],
    )
    ap = [{"kind": "AP", "label": "AP Fake", "maps_to": "FAKE 10000", "units": 100}]
    same = verify(plan({AU1: ["FAKE 10000"]}, credits=ap), ruleset(), cat, only("V02"))
    assert "forfeited" in found(same, "V02", "error")[0].message
    equivalent = verify(plan({AU1: ["FAKE 16000"]}, credits=ap), ruleset(), cat, only("V02"))
    assert "forfeited because the equivalent" in found(equivalent, "V02", "error")[0].message
    exam_item = plan({AU1: [{"course": "FAKE 10000", "status": "exam"}], WI1: ["FAKE 10000"]})
    assert "forfeited" in verify(exam_item, ruleset(), cat, only("V02")).issues[0].message
    both = verify(plan({AU1: ["FAKE 16000"], WI1: ["FAKE 17000"]}), ruleset(), cat, only("V02"))
    assert "equivalent courses" in found(both, "V02", "error")[0].message
    assert not verify(plan(credits=ap), ruleset(), cat, only("V02")).issues


# ----------------------------------------------------------------------------------- V03


def test_v03_prerequisite_in_the_same_term_is_an_error() -> None:
    cat = catalog(["FAKE 10000", "FAKE 10100"])
    rules = ruleset(prereqs={"FAKE 10100": "FAKE 10000"})
    report = verify(plan({AU1: ["FAKE 10000", "FAKE 10100"]}), rules, cat, only("V03"))
    (issue,) = found(report, "V03", "error")
    assert issue.course_ids == ["FAKE 10100"] and issue.term_ids == [AU1]
    assert "FAKE 10000 is in 2026-AU, which is not before 2026-AU" in issue.message
    assert issue.fix_hints == ["Move FAKE 10000 before 2026-AU, or move FAKE 10100 later."]
    ok = verify(plan({AU1: ["FAKE 10000"], WI1: ["FAKE 10100"]}), rules, cat, only("V03"))
    assert ok.status == "valid"
    missing = verify(plan({WI1: ["FAKE 10100"]}), rules, cat, only("V03"))
    assert missing.issues[0].fix_hints == ["Add FAKE 10000 before 2027-WI."]


def test_v03_co_requisite_in_the_same_term_is_ok() -> None:
    cat = catalog(["FAKE 10000", "FAKE 10100", "FAKE 10200"])
    rules = ruleset(
        prereqs={"FAKE 10100": {"concurrent": "FAKE 10000"}},
        requisites=[Requisite.model_validate({"course": "FAKE 10200", "coreq": "FAKE 10000"})],
    )
    same = plan({AU1: ["FAKE 10000", "FAKE 10100", "FAKE 10200"]})
    report = verify(same, rules, cat, only("V03", "V07"))
    assert report.status == "valid" and report.certificate is not None
    assert check_certificate(same, rules, cat, report.certificate)
    assert {w.course: w.by for w in report.certificate.prereq_witnesses} == {
        "FAKE 10100": ["FAKE 10000@2026-AU"],
        "FAKE 10200": ["FAKE 10000@2026-AU"],
    }
    later = plan({AU1: ["FAKE 10100", "FAKE 10200"], WI1: ["FAKE 10000"]})
    report = verify(later, rules, cat, only("V03"))
    assert len(found(report, "V03", "error")) == 2
    assert any(i.message.startswith("Co-requisite of FAKE 10200") for i in report.issues)
    assert "in or before" in report.issues[0].message


def test_v03_consent_is_a_warning_and_the_cheapest_branch_wins() -> None:
    cat = catalog(["FAKE 10000", "FAKE 20000", "FAKE 20100"])
    rules = ruleset(
        prereqs={
            "FAKE 20000": {"all": ["FAKE 10000", {"consent": "instructor"}]},
            "FAKE 20100": {"any": [{"consent": "department"}, "FAKE 10000"]},
        }
    )
    p = plan({AU1: ["FAKE 10000"], WI1: ["FAKE 20000", "FAKE 20100"]})
    report = verify(p, rules, cat, only("V03", "V07"))
    assert report.status == "warnings" and error_codes(report) == set()
    (warning,) = found(report, "V03", "warning")
    assert warning.course_ids == ["FAKE 20000"] and "consent of the instructor" in warning.message
    assert report.certificate is not None and check_certificate(p, rules, cat, report.certificate)
    by = {w.course: w.by for w in report.certificate.prereq_witnesses}
    assert by["FAKE 20100"] == ["FAKE 10000@2026-AU"]
    assert by["FAKE 20000"] == ["FAKE 10000@2026-AU", "consent:instructor"]
    # without the course, consent is the only way in
    alone = verify(plan({WI1: ["FAKE 20100"]}), rules, cat, only("V03"))
    assert warning_codes(alone) == {"V03"} and "department" in alone.issues[0].message


def test_v03_credits_placement_standing_program_and_n_of() -> None:
    cat = catalog(
        ["FAKE 10000", "FAKE 15000", "FAKE 20000", "FAKE 21000", "FAKE 22000", "FAKE 23000"],
        relations=[{"a": "FAKE 15000", "b": "FAKE 10000", "kind": "equivalent"}],
    )
    rules = ruleset(
        program("fake-ba", SLOT),
        prereqs={
            "FAKE 20000": {
                "n_of": 2,
                "of": ["FAKE 10000", {"placement": "FAKE 15100"}, "FAKE 23000"],
            },
            "FAKE 21000": {"standing": "third-year"},
        },
        requisites=[
            Requisite.model_validate(
                {"course": "FAKE 22000", "restrictions": {"program": "fake-*"}}
            )
        ],
    )
    p = plan(
        {AU1: ["FAKE 20000", "FAKE 22000"], T[6]: ["FAKE 21000"]},
        programs=["fake-ba"],
        credits=[{"kind": "AP", "label": "AP", "maps_to": "FAKE 15000"}],
        placements=["FAKE 15100"],
    )
    report = verify(p, rules, cat, only("V03"))
    assert not report.issues
    # equivalent credit + placement credit satisfy 2 of 3; standing holds in year 3
    bad = plan(
        {AU1: ["FAKE 20000", "FAKE 22000"], T[3]: ["FAKE 21000"]},
        credits=[{"kind": "placement", "label": "FAKE 15100"}],
    )
    report = verify(bad, rules, cat, only("V03"))
    messages = " | ".join(i.message for i in found(report, "V03", "error"))
    assert (
        "FAKE 10000 is not in the plan" in messages and "FAKE 23000 is not in the plan" in messages
    )
    assert "is not recorded" not in messages  # the placement credit counts
    assert "third-year standing is needed in 2027-AU" in messages
    assert (
        "Restriction of FAKE 22000" in messages and "restricted to students in fake-*" in messages
    )
    none = verify(plan({AU1: ["FAKE 20000"]}), rules, cat, only("V03"))
    assert "placement into FAKE 15100 is not recorded" in none.issues[0].message
    transfer = plan({AU1: ["FAKE 20000"]}, entry_year_level=3)
    transfer = transfer.model_copy(
        update={"items": [*transfer.items, *plan({AU1: ["FAKE 21000"]}).items]}
    )
    assert "FAKE 21000" not in " ".join(
        i.message for i in verify(transfer, rules, cat, only("V03")).issues
    )


def test_v03_min_grade_and_history() -> None:
    cat = catalog(["FAKE 10000", "FAKE 10100"])
    rules = ruleset(prereqs={"FAKE 10100": {"course": "FAKE 10000", "min_grade": "C-"}})

    def run(**first: object) -> object:
        p = plan({AU1: [{"course": "FAKE 10000", **first}], WI1: ["FAKE 10100"]})
        return verify(p, rules, cat, only("V03"))

    low = run(status="completed", grade="D")
    assert "has grade D, below the required C-" in low.issues[0].message  # type: ignore[attr-defined]
    assert run(status="completed", grade="B").status == "valid"  # type: ignore[attr-defined]
    planned = run()
    assert planned.status == "valid"  # type: ignore[attr-defined]
    assert planned.assumptions == [  # type: ignore[attr-defined]
        "Courses without a recorded grade are assumed to meet grade minimums."
    ]
    # completed courses are history: their prerequisites are not re-checked
    done = plan({AU1: [{"course": "FAKE 10100", "status": "completed"}]})
    assert verify(done, rules, cat, only("V03")).status == "valid"


# ----------------------------------------------------------------------------------- V04


def test_v04_low_p_offered_warns() -> None:
    cat = catalog(
        ["FAKE 10000", "FAKE 10100"],
        offerings=[
            {"course": "FAKE 10000", "quarter": "AU", "p_offered": 0.95},
            {"course": "FAKE 10000", "quarter": "WI", "p_offered": 0.2},
            {"course": "FAKE 10000", "quarter": "SP", "p_offered": 0.3},
        ],
    )
    report = verify(plan({WI1: ["FAKE 10000", "FAKE 10100"]}), ruleset(), cat, only("V04"))
    (issue,) = report.issues
    assert (issue.code, issue.level, issue.course_ids) == ("V04", "warning", ["FAKE 10000"])
    assert "not usually offered in Winter (estimated chance 20%)" in issue.message
    assert issue.fix_hints == ["Move FAKE 10000 to Autumn or Spring."]
    assert report.status == "warnings"
    # exactly 0.3 does not warn; a quarter without a pattern counts as 0; history is not flagged
    assert not verify(plan({SP1: ["FAKE 10000"]}), ruleset(), cat, only("V04")).issues
    summer = verify(plan({"2027-SU": ["FAKE 10000"]}), ruleset(), cat, only("V04"))
    assert "Summer (estimated chance 0%)" in summer.issues[0].message
    done = plan({WI1: [{"course": "FAKE 10000", "status": "completed"}]})
    assert not verify(done, ruleset(), cat, only("V04")).issues
    never = catalog(
        ["FAKE 10000"], offerings=[{"course": "FAKE 10000", "quarter": "AU", "p_offered": 0.1}]
    )
    hint = verify(plan({AU1: ["FAKE 10000"]}), ruleset(), never, only("V04")).issues[0].fix_hints
    assert hint == ["Check with the department when FAKE 10000 will be offered."]


def test_v04_posted_schedule_wins() -> None:
    sections = [
        {"term": WI1, "course": "FAKE 10100", "section_no": "1"},
        {"term": WI1, "course": "FAKE 10200", "section_no": "1", "status": "Cancelled"},
    ]
    cat = catalog(
        ["FAKE 10000", "FAKE 10100", "FAKE 10200"],
        sections=sections,
        offerings=[
            {"course": "FAKE 10000", "quarter": "WI", "p_offered": 0.95},
            {"course": "FAKE 10100", "quarter": "WI", "p_offered": 0.05},
        ],
    )
    report = verify(
        plan({WI1: ["FAKE 10000", "FAKE 10100", "FAKE 10200"]}), ruleset(), cat, only("V04")
    )
    assert [(i.level, i.course_ids) for i in report.issues] == [
        ("error", ["FAKE 10000"]),
        ("error", ["FAKE 10200"]),
    ]
    assert "not on the posted schedule for 2027-WI" in report.issues[0].message


# ----------------------------------------------------------------------------------- V05

LOADS = dict(full_time_min_units=300, full_time_max_units=400, overload_units=500)
REASONS = [
    {"id": "grad-need", "label": "Graduation need in the fourth year", "year": 4},
    {
        "id": "research",
        "label": "Reading and Research",
        "course_selector": {"codes": ["FAKE 29700"]},
    },
    {"id": "language", "label": "A 200-unit language course", "min_course_units": 200},
]
FIVE = ["FAKE 10000", "FAKE 10100", "FAKE 10200", "FAKE 10300", "FAKE 10400"]


def test_v05_500_units_with_and_without_an_overload_reason() -> None:
    cat = catalog([*FIVE, "FAKE 29700", course("LANG 10100", units=200)])
    rules = ruleset(college=college(**LOADS, overload_reasons=REASONS))
    without = verify(plan({T[9]: FIVE}), rules, cat, only("V05"))
    (issue,) = found(without, "V05", "error")
    assert "500 units; more than 400 units needs an overload reason" in issue.message
    assert issue.fix_hints == [
        "Move a course out of 2029-AU.",
        "Claim the overload reason 'Graduation need in the fourth year' (grad-need).",
    ]
    claimed = plan({T[9]: FIVE}, overload_reasons={T[9]: "grad-need"})
    report = verify(claimed, rules, cat, only("V05"))
    assert report.status == "warnings" and "needs a petition" in report.issues[0].message
    # the same reason in the first year does not apply; an unknown reason id neither
    early = verify(
        plan({T[0]: FIVE}, overload_reasons={T[0]: "grad-need"}), rules, cat, only("V05")
    )
    assert "does not apply to this quarter" in found(early, "V05", "error")[0].message
    unknown = verify(plan({T[0]: FIVE}, overload_reasons={T[0]: "nope"}), rules, cat, only("V05"))
    assert error_codes(unknown) == {"V05"}
    # course-based reasons
    research = [*FIVE[:4], "FAKE 29700"]
    ok = verify(
        plan({T[0]: research}, overload_reasons={T[0]: "research"}), rules, cat, only("V05")
    )
    assert ok.status == "warnings"
    lang = [*FIVE[:3], "LANG 10100"]
    ok = verify(plan({T[0]: lang}, overload_reasons={T[0]: "language"}), rules, cat, only("V05"))
    assert ok.status == "warnings"
    no = verify(plan({T[0]: FIVE}, overload_reasons={T[0]: "language"}), rules, cat, only("V05"))
    assert no.status == "errors"
    # 600 units is never allowed
    six = verify(
        plan({T[9]: [*FIVE, "FAKE 29700"]}, overload_reasons={T[9]: "grad-need"}),
        rules,
        cat,
        only("V05"),
    )
    assert "the most a quarter can carry is 500" in found(six, "V05", "error")[0].message


def test_v05_bounds_empty_quarters_summer_history_and_placeholders() -> None:
    cat = catalog(FIVE)
    rules = ruleset(college=college(**LOADS))
    p = plan(
        {
            T[0]: FIVE[:2],  # 200 units: below full time
            # T[1] is empty: not flagged
            T[2]: [*FIVE[:2], {"slot_ref": "x/y"}],  # a placeholder counts 100 units
            "2027-SU": FIVE[:1],  # Summer is not checked
            T[3]: [{"course": c, "status": "completed"} for c in FIVE[:2]],  # history
            T[4]: [*FIVE[:3], {"course": "FAKE 10300", "status": "transfer"}],  # transfer: no load
        }
    )
    report = verify(p, rules, cat, only("V05"))
    assert [(i.level, i.term_ids) for i in report.issues] == [("error", [T[0]]), ("info", [T[3]])]
    assert "200 units; a full-time quarter needs at least 300" in report.issues[0].message
    assert report.status == "errors"
    # an info issue alone leaves the plan valid
    history = plan({T[3]: [{"course": c, "status": "completed"} for c in FIVE[:2]]})
    assert verify(history, rules, cat, only("V05")).status == "valid"


def test_v05_without_policy_values_is_an_assumption() -> None:
    cat = catalog(FIVE)
    none = verify(plan({T[0]: FIVE}), ruleset(), cat, only("V05"))
    assert not none.issues and "No College policy is loaded" in none.assumptions[0]
    empty = verify(plan({T[0]: FIVE}), ruleset(college=college()), cat, only("V05"))
    assert not empty.issues and "full-time load" in empty.assumptions[0]
    no_cap = ruleset(college=college(full_time_min_units=300, full_time_max_units=400))
    report = verify(plan({T[0]: FIVE}), no_cap, cat, only("V05"))
    assert "the most a quarter can carry is 400" in report.issues[0].message


# ----------------------------------------------------------------------------------- V06


def _section(
    code: str, no: str, start: str, end: str, component: str = "LEC", days: str = "MO"
) -> dict[str, object]:
    return {
        "term": AU1,
        "course": code,
        "section_no": no,
        "component": component,
        "meetings": [{"days": [days], "start": start, "end": end}],
    }


def test_v06_clash_only_when_no_pair_of_sections_fits() -> None:
    cat = catalog(
        ["FAKE 10000", "FAKE 10100", "FAKE 10200", "FAKE 10300"],
        sections=[
            _section("FAKE 10000", "1", "09:30", "10:50"),
            _section("FAKE 10100", "1", "10:00", "11:20"),
            _section("FAKE 10200", "1", "10:00", "11:20"),
            _section("FAKE 10200", "2", "13:00", "14:20"),  # an alternative that fits
            _section("FAKE 10300", "1", "09:30", "10:50", days="TU"),
            {"term": AU1, "course": "FAKE 10300", "section_no": "L1", "component": "LAB"},
        ],
    )
    p = plan({AU1: ["FAKE 10000", "FAKE 10100", "FAKE 10200", "FAKE 10300"], WI1: ["FAKE 10000"]})
    report = verify(p, ruleset(), cat, only("V06"))
    (issue,) = report.issues
    assert (issue.code, issue.level) == ("V06", "warning")
    assert issue.course_ids == ["FAKE 10000", "FAKE 10100"] and issue.term_ids == [AU1]
