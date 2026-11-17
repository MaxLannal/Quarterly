"""V11: one test per goal type in SPEC "Goal predicates", on fake fixtures."""

from typing import Any

from core_support import T, catalog, course, found, plan, program, ruleset
from planner_core import check_certificate, verify
from planner_core.models import Certificate, PlanState, Report, RuleSet, VerifyOptions

OPTS = VerifyOptions(checks=["V03", "V07", "V11"])
CODES = [f"FAKE {20000 + 100 * i}" for i in range(8)]


def attributes(
    key: str, values: dict[str, float], ci_high: float | None = None
) -> list[dict[str, Any]]:
    return [
        {"subject_id": c, "key": key, "value": v, "ci_high": ci_high} for c, v in values.items()
    ]


CAT = catalog(
    [
        *[course(c, tags=["theory"] if i < 3 else []) for i, c in enumerate(CODES)],
        "ABRD 20100",
        "ABRD 20200",
        "LANG 10100",
        "LANG 10200",
        "LANG 10300",
        "PMED 10100",
        "PMED 10200",
    ],
    course_lists=[
        {"name": "premed", "courses": ["PMED 10100", "PMED 10200"]},
        {"name": "lang-seq", "courses": ["LANG 10100", "LANG 10200", "LANG 10300"]},
    ],
    attributes=[
        *attributes(
            "workload_hours", {CODES[0]: 10, CODES[1]: 12, CODES[2]: 14, CODES[3]: 8}, ci_high=16
        ),
        *attributes("difficulty", {CODES[0]: 4.5, CODES[1]: 4.0, CODES[2]: 2.0, CODES[3]: 3.0}),
        *attributes("grading_strictness", {CODES[0]: 4.5, CODES[1]: 4.2, CODES[2]: 2.0}),
        {"subject_type": "course_instructor", "subject_id": "77", "key": "difficulty", "value": 5},
    ],
)
BLOCK = program(
    "paris-civ",
    {
        "group": {
            "all": True,
            "children": [
                {"slot": {"any_of": ["ABRD 20100"]}},
                {"select": {"count": 1, "from": {"subject": "ABRD"}}},
            ],
        }
    },
    type="study_abroad_block",
)
BXMS = program(
    "fake-bxms",
    {"select": {"count": 1, "from": {"subject": "FAKE"}}},
    type="bxms",
    policy={"timing": {"apply_requires": [CODES[0], CODES[1]]}},
)
MAJOR = program(
    "fake-ba",
    {
        "group": {
            "all": True,
            "children": [
                {"slot": {"any_of": [CODES[7]]}},
                {"select": {"count": 1, "from": {"subject": "FAKE"}}},
            ],
        }
    },
)
RULES = ruleset(BLOCK, BXMS, MAJOR)


def run(
    goal: dict[str, Any], items: dict[str, list[Any]], rules: RuleSet = RULES, **fields: Any
) -> tuple[Report, Any]:
    """Verify a plan with one goal; return the report and the goal's (value, limit, pass)."""
    p = plan(items, goals=[{"id": "g1", **goal}], **fields)
    report = verify(p, rules, CAT, fields.pop("options", OPTS))
    issues = found(report, "V11")
    if report.certificate is not None:
        assert check_certificate(p, rules, CAT, report.certificate)
        (result,) = report.certificate.goals
        assert result.pass_ == (not issues)
        return report, (result.value, result.limit, result.pass_)
    assert issues and issues[0].level == "error" and issues[0].goal_id == "g1"
    return report, None


def soft_and_hard(
    goal: dict[str, Any], items: dict[str, list[Any]], **fields: Any
) -> tuple[Report, Any]:
    """A failing goal: soft -> warning with a score and a certificate; hard -> error."""
    soft, result = run(goal, items, **fields)
    (warning,) = found(soft, "V11")
    assert warning.level == "warning" and "(soft goal, score " in warning.message
    assert warning.fix_hints and result is not None and result[2] is False
    hard, _ = run({**goal, "hard": True}, items, **fields)
    assert hard.status == "errors" and hard.certificate is None
    assert "soft goal" not in found(hard, "V11", "error")[0].message
    return soft, result


def test_course_load() -> None:
    items = {T[0]: CODES[:4], T[1]: CODES[4:6], "2027-SU": CODES[6:7]}
    _, result = run({"type": "course_load", "min_courses": 2, "max_courses": 4}, items)
    assert result == (4.0, 4.0, True)
    soft, result = soft_and_hard({"type": "course_load", "max_courses": 3}, items)
    assert result == (4.0, 3.0, False)
    assert found(soft, "V11")[0].term_ids == [T[0]]
    _, result = soft_and_hard({"type": "course_load", "min_courses": 3}, items)  # Summer is skipped
    assert result == (2.0, 3.0, False)
    _, result = run({"type": "course_load", "scope": "term", "term": T[1], "max_courses": 2}, items)
    assert result == (2.0, 2.0, True)
    _, result = run({"type": "course_load", "min_courses": 1}, {})
    assert result == (0.0, 1.0, True)  # no quarters planned yet: nothing to flag


def test_workload_hours() -> None:
    items = {T[0]: CODES[:3], T[1]: [CODES[3], CODES[4]]}  # 36 h, then 8 h (+ one unknown)
    report, result = run({"type": "workload_hours", "max_hours": 36}, items)
    assert result == (36.0, 36.0, True)
    assert report.assumptions == ["No workload estimate for FAKE 20400; counted as 0."]
    soft, result = soft_and_hard({"type": "workload_hours", "max_hours": 30}, items)
    assert result == (36.0, 30.0, False) and found(soft, "V11")[0].term_ids == [T[0]]
    assert "score 0.83" in found(soft, "V11")[0].message
    _, result = run(
        {"type": "workload_hours", "max_hours": 30, "aggregate": "career_average"}, items
    )
    assert result == (22.0, 30.0, True)
    _, result = soft_and_hard(
        {"type": "workload_hours", "max_hours": 20, "aggregate": "career_average"}, items
    )
    assert result == (22.0, 20.0, False)
    # strict: the upper confidence bound (16 h per course with an estimate)
    _, result = run({"type": "workload_hours", "max_hours": 48, "strict": True}, items)
    assert result == (48.0, 48.0, True)
    strict = VerifyOptions(checks=["V03", "V07", "V11"], strictness="strict")
    p = plan(items, goals=[{"id": "g1", "type": "workload_hours", "max_hours": 40}])
    report = verify(p, RULES, CAT, strict)
    assert found(report, "V11", "warning") and report.certificate is not None
    assert report.certificate.goals[0].value == 48.0
    assert check_certificate(p, RULES, CAT, report.certificate)  # accepted under either strictness


def test_difficulty_cap() -> None:
    items = {T[0]: CODES[:3], T[1]: [CODES[3]]}  # 10.5 with two very hard, then 3.0
    _, result = run({"type": "difficulty_cap", "max_index": 10.5}, items)
    assert result == (10.5, 10.5, True)
    _, result = soft_and_hard({"type": "difficulty_cap", "max_index": 9}, items)
    assert result == (10.5, 9.0, False)
    _, result = run({"type": "difficulty_cap", "max_very_hard": 2}, items)
    assert result == (2.0, 2.0, True)
    soft, result = soft_and_hard({"type": "difficulty_cap", "max_very_hard": 1}, items)
    assert (
        result == (2.0, 1.0, False)
        and "number of very hard courses" in found(soft, "V11")[0].message
    )
    _, result = run(
        {"type": "difficulty_cap", "max_very_hard": 1, "very_hard_threshold": 4.5}, items
    )
    assert result == (1.0, 1.0, True)
    _, result = soft_and_hard(
        {"type": "difficulty_cap", "max_index": 20, "max_very_hard": 1}, items
    )
    assert result == (2.0, 1.0, False)


def test_challenge() -> None:
    items = {T[0]: CODES[:3], T[1]: [CODES[3]]}  # 10.5 and 3.0: average 6.75
    _, result = run({"type": "challenge", "min_index": 6.5}, items)
    assert result == (6.75, 6.5, True)
    _, result = soft_and_hard({"type": "challenge", "min_index": 8}, items)
    assert result == (6.75, 8.0, False)
    _, result = soft_and_hard(
        {"type": "challenge", "scope": "term", "term": T[1], "min_index": 4}, items
    )
    assert result == (3.0, 4.0, False)
    _, result = soft_and_hard({"type": "challenge", "min_index": 1}, {})
    assert result == (0.0, 1.0, False)


def test_protect_gpa() -> None:
    soft, result = soft_and_hard({"type": "protect_gpa"}, {T[0]: CODES[:3]})
    assert result == (2.0, 1.0, False)
    assert found(soft, "V11")[0].course_ids == CODES[:2]
    _, result = run({"type": "protect_gpa"}, {T[0]: [CODES[0], CODES[2]], T[1]: [CODES[1]]})
    assert result == (1.0, 1.0, True)
    _, result = run({"type": "protect_gpa", "strictness_threshold": 4.4}, {T[0]: CODES[:3]})
    assert result == (1.0, 1.0, True)


def test_graduate_by() -> None:
    items = {T[0]: CODES[:2], T[8]: CODES[2:4], T[9]: [CODES[4], {"slot_ref": "x"}]}
    _, result = run({"type": "graduate_by", "by_term": "Y4-AU"}, items)
    assert result == (0.0, 0.0, True)
    soft, result = soft_and_hard({"type": "graduate_by", "by_term": "Y3-SP"}, items)
    assert result == (2.0, 0.0, False) and found(soft, "V11")[0].term_ids == [T[9]]
    _, result = run({"type": "graduate_by", "by_term": "2030-SP"}, items)
    assert result[2] is True


def test_study_abroad() -> None:
    goal = {"type": "study_abroad", "program_id": "paris-civ", "abroad_term": "Y3-AU"}
    abroad = {T[0]: CODES[:1], T[6]: ["ABRD 20100", "ABRD 20200", {"slot_ref": "paris-civ/2"}]}
    _, result = run(goal, abroad, programs=["paris-civ"])
    assert result == (0.0, 0.0, True)
    soft, result = soft_and_hard(
        goal,
        {T[6]: ["ABRD 20100", "ABRD 20200", CODES[0], {"slot_ref": "fake-ba"}]},
        programs=["paris-civ"],
    )
    assert result == (2.0, 0.0, False)
    assert "2 on-campus course(s) are planned in 2028-AU" in found(soft, "V11")[0].message
    assert found(soft, "V11")[0].course_ids == [CODES[0]]
    # the block is not listed in the plan
    soft, result = soft_and_hard(goal, abroad)
    assert (
        result == (None, 0.0, False)
        and "not one of the plan's programs" in found(soft, "V11")[0].message
    )
    # the block's courses sit in another term: the block is "not fully placed"; V07 passes
    opts = VerifyOptions(checks=["V03", "V11"])
    p = plan(
        {T[5]: ["ABRD 20100"], T[6]: ["ABRD 20200"]},
        programs=["paris-civ"],
        goals=[{"id": "g1", **goal}],
    )
    report = verify(p, RULES, CAT, opts)
    assert "is not fully placed in 2028-AU" in found(report, "V11", "warning")[0].message


def test_bxms() -> None:
    goal = {"type": "bxms", "program_id": "fake-bxms", "apply_by": "Y3-WI"}
    _, result = run(goal, {T[5]: CODES[:1], T[6]: CODES[1:2]}, programs=["fake-bxms"])
    assert result == (0.0, 0.0, True)
    # "before" is strict: a prerequisite in the application quarter is late
    soft, result = soft_and_hard(goal, {T[5]: CODES[:1], T[7]: CODES[1:2]}, programs=["fake-bxms"])
    assert result == (1.0, 0.0, False)
    assert (
        found(soft, "V11")[0].course_ids == [CODES[1]]
        and "score 0.50" in found(soft, "V11")[0].message
    )
    assert found(soft, "V11")[0].fix_hints == ["Schedule FAKE 20100 before 2029-WI."]
    _, result = soft_and_hard(goal, {T[5]: CODES[:2]})
    assert result == (None, 0.0, False)
    report, result = run(
        {**goal, "program_id": "fake-ba"}, {T[5]: [CODES[7], CODES[0]]}, programs=["fake-ba"]
    )
    assert result == (0.0, 0.0, True)
    assert "No application prerequisites are encoded for fake-ba." in report.assumptions


def test_premed() -> None:
    goal = {"type": "premed", "list": "premed", "courses": [CODES[0]], "complete_by": "Y2-SP"}
    done = {T[0]: ["PMED 10100", CODES[0]], T[5]: ["PMED 10200"]}
    _, result = run(goal, done)
    assert result == (0.0, 0.0, True)
    soft, result = soft_and_hard(goal, {T[0]: ["PMED 10100"], T[6]: ["PMED 10200"]})
    assert result == (2.0, 0.0, False)
    assert found(soft, "V11")[0].course_ids == [CODES[0], "PMED 10200"]
    assert "score 0.33" in found(soft, "V11")[0].message
    credit = plan(
        credits=[
            {"kind": "transfer", "label": "t", "maps_to": c}
            for c in ("PMED 10100", "PMED 10200", CODES[0])
        ],
        goals=[{"id": "g1", **goal}],
    )
    assert not found(verify(credit, RULES, CAT, OPTS), "V11")


def test_interest() -> None:
    # CODES[7] fills a slot of the major, so it is not an elective; 2 of the 4 others are tagged
    items = {T[0]: [CODES[7], CODES[0], CODES[1], CODES[3], CODES[4]]}
    _, result = run(
        {"type": "interest", "tags": ["theory"], "min_share": 0.5}, items, programs=["fake-ba"]
    )
    assert result == (0.5, 0.5, True)
    soft, result = soft_and_hard(
        {"type": "interest", "tags": ["theory"], "min_share": 0.75}, items, programs=["fake-ba"]
    )
    assert result == (0.5, 0.75, False) and "50% of electives" in found(soft, "V11")[0].message
    _, result = run({"type": "interest", "tags": ["theory"]}, {})
    assert result == (0.0, None, True)


def test_light_quarter() -> None:
    _, result = run({"type": "light_quarter", "term": T[1], "max_courses": 3}, {T[1]: CODES[:3]})
    assert result == (3.0, 3.0, True)
    soft, result = soft_and_hard(
        {"type": "light_quarter", "term": T[1], "max_courses": 3},
        {T[1]: [*CODES[:3], {"slot_ref": "x"}]},
    )
    assert result == (4.0, 3.0, False)
    assert found(soft, "V11")[0].fix_hints == ["Move 1 course(s) out of 2027-WI."]


def test_language() -> None:
    goal = {
        "type": "language",
        "language": "Fakish",
        "level": "first-year",
        "by_term": "Y1-SP",
        "list": "lang-seq",
    }
    done = {T[0]: ["LANG 10100"], T[1]: ["LANG 10200"], T[2]: ["LANG 10300"]}
    _, result = run(goal, done)
    assert result == (0.0, 0.0, True)
    soft, result = soft_and_hard(
        goal, {T[0]: ["LANG 10100"], T[1]: ["LANG 10200"], T[3]: ["LANG 10300"]}
    )
    assert result == (1.0, 0.0, False)
    assert "Fakish (first-year): LANG 10300 not done by 2027-SP." in found(soft, "V11")[0].message
    soft, result = soft_and_hard({**goal, "list": None}, done)
    assert result == (None, 0.0, False) and "cannot be checked" in found(soft, "V11")[0].message
    _, result = run({**goal, "list": None, "courses": ["LANG 10300"]}, done)
    assert result == (0.0, 0.0, True)


def test_a_tampered_goal_result_is_rejected() -> None:
    goal = {"id": "g1", "type": "light_quarter", "term": T[1], "max_courses": 3}
    p = plan({T[1]: CODES[:4]}, goals=[goal])
    report = verify(p, RULES, CAT, OPTS)
    cert = report.certificate
    assert cert is not None and check_certificate(p, RULES, CAT, cert)
    forged = cert.model_dump()
    forged["goals"][0].update({"pass": True, "value": 3.0})
    assert not check_certificate(p, RULES, CAT, Certificate.model_validate(forged))
    assert not check_certificate(p, RULES, CAT, cert.model_copy(update={"goals": []}))
    # a hard goal that fails can never be certified, even if the result is reported honestly
    hard = PlanState.model_validate({**p.model_dump(), "goals": [{**goal, "hard": True}]})
    honest = cert.model_copy(update={"plan_hash": verify(hard, RULES, CAT).plan_hash})
    assert not check_certificate(hard, RULES, CAT, honest)
