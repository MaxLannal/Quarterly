"""Hypothesis properties (SPEC "Testing"): every certificate the verifier issues passes
`check_certificate`; mutating a valid plan (drop a course, move it one term earlier, add a
fifth course) produces the expected issue codes; a tampered certificate is rejected."""

from typing import Any

from core_support import T, catalog, college, course, error_codes, plan, program, ruleset
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from planner_core import check_certificate, verify, verify_checked
from planner_core.models import Certificate, PlanState

INTRO = ["INTR 10100", "INTR 10200", "INTR 10300"]
ELEC = [f"ELEC {20000 + 100 * i}" for i in range(8)]
MINR = [f"MINR {20000 + 100 * i}" for i in range(4)]
ARTS = ["ARTS 10100", "ARTS 10200", "ARTS 10300"]
FILL = [f"FILL {10000 + 100 * i}" for i in range(44)]
CAT = catalog(
    [*INTRO, *ELEC, *MINR, *[course(c, core_tags=["arts"]) for c in ARTS], "LANG 10300", *FILL]
)
MAJOR = program(
    "w-bs",
    {
        "group": {
            "all": True,
            "children": [
                {
                    "id": "intro",
                    "group": {"all": True, "children": [{"slot": {"any_of": [c]}} for c in INTRO]},
                },
                {"id": "electives", "select": {"count": 4, "from": {"subject": "ELEC"}}},
            ],
        }
    },
)
MINOR = program(
    "w-minor",
    {"select": {"count": 3, "from": {"union": [{"subject": "ELEC"}, {"subject": "MINR"}]}}},
    type="minor",
    policy={"share": [{"with": "type:major", "max": 1}]},
)
CORE = program(
    "core",
    {
        "group": {
            "all": True,
            "children": [
                {"id": "language", "slot": {"any_of": ["LANG 10300"]}},
                {"id": "arts", "select": {"count": 2, "from": {"tags": ["core:arts"]}}},
            ],
        }
    },
    type="core",
)
POLICY = college(
    total_units=4200,
    units_by_enrollment=3800,
    full_time_min_units=300,
    full_time_max_units=400,
    overload_units=500,
    overload_reasons=[{"id": "grad-need", "label": "Graduation need", "year": 4}],
    language_node="core/language",
    core_complete_by="Y2-SP",
    residency_min_fraction=0.5,
    max_quarters=12,
)
PREREQS: dict[str, Any] = {
    "INTR 10200": "INTR 10100",
    "INTR 10300": "INTR 10200",
    **{
        c: ("INTR 10100" if i % 2 else {"any": ["INTR 10200", {"placement": "x"}]})
        for i, c in enumerate(ELEC)
    },
}
RULES = ruleset(MAJOR, MINOR, CORE, college=POLICY, prereqs=PREREQS)
PROGRAMS = ["w-bs", "w-minor", "core"]
SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@st.composite
def valid_plans(draw: st.DrawFn) -> PlanState:
    """A complete plan: 4 courses in each of 12 quarters, every rule met."""
    electives = draw(st.lists(st.sampled_from(ELEC), min_size=4, max_size=6, unique=True))
    minors = draw(st.lists(st.sampled_from(MINR), min_size=2, max_size=4, unique=True))
    arts = draw(st.lists(st.sampled_from(ARTS), min_size=2, max_size=2, unique=True))
    head = [
        [INTRO[0], arts[0], FILL[0], FILL[1]],
        [INTRO[1], "LANG 10300", FILL[2], FILL[3]],
        [INTRO[2], arts[1], FILL[4], FILL[5]],
    ]
    rest = [*electives, *minors]
    rest += FILL[6 : 6 + 36 - len(rest)]
    rest = draw(st.permutations(rest))
    terms = head + [list(rest[i : i + 4]) for i in range(0, 36, 4)]
    return plan({T[i]: courses for i, courses in enumerate(terms)}, programs=PROGRAMS)


def without(p: PlanState, code: str) -> PlanState:
    return p.model_copy(update={"items": [i for i in p.items if i.course != code]})


def moved(p: PlanState, code: str, term: str) -> PlanState:
    items = [i.model_copy(update={"term": term}) if i.course == code else i for i in p.items]
    return p.model_copy(update={"items": items})


@SETTINGS
@given(valid_plans())
def test_valid_plans_get_a_certificate_the_checker_accepts(p: PlanState) -> None:
    report = verify(p, RULES, CAT)
    assert error_codes(report) == set(), [i.message for i in report.issues]
    assert report.certificate is not None
    assert check_certificate(p, RULES, CAT, report.certificate)
    checked, problems = verify_checked(p, RULES, CAT)
    assert problems == [] and checked == report
    # deterministic, and the certificate survives a JSON round trip
    assert verify(p, RULES, CAT) == report
    again = Certificate.model_validate_json(report.certificate.model_dump_json())
    assert check_certificate(p, RULES, CAT, again)


@SETTINGS
@given(valid_plans(), st.data())
def test_dropping_a_required_course_is_caught(p: PlanState, data: st.DataObject) -> None:
    code = data.draw(st.sampled_from([*INTRO, "LANG 10300", *ARTS]))
    if code not in {i.course for i in p.items}:
        return
    report = verify(without(p, code), RULES, CAT)
    codes = error_codes(report)
    assert "V07" in codes and report.certificate is None
    assert ("V03" in codes) == (code in INTRO[:2])  # later courses lose their prerequisite
    assert ("V09" in codes) == (code not in INTRO)  # the Core is incomplete
    unmet = {i.node_id for i in report.issues if i.code == "V07"}
    assert any(node.startswith("core" if code not in INTRO else "w-bs/intro") for node in unmet)


@SETTINGS
@given(valid_plans(), st.data())
def test_dropping_any_course_never_yields_a_bad_certificate(
    p: PlanState, data: st.DataObject
) -> None:
    code = data.draw(st.sampled_from([i.course for i in p.items]))
    smaller = without(p, code)
    report = verify(smaller, RULES, CAT)
    if report.certificate is None:
        assert report.status == "errors"
    else:
        assert check_certificate(smaller, RULES, CAT, report.certificate)
        # the certificate of the full plan does not fit the smaller plan
        assert not check_certificate(smaller, RULES, CAT, verify(p, RULES, CAT).certificate)  # type: ignore[arg-type]


@SETTINGS
@given(valid_plans(), st.data())
def test_moving_a_course_one_term_earlier(p: PlanState, data: st.DataObject) -> None:
    item = data.draw(st.sampled_from([i for i in p.items if i.term != T[0]]))
    assert item.course is not None
    earlier = moved(p, item.course, T[T.index(item.term) - 1])
    report = verify(earlier, RULES, CAT)
    codes = error_codes(report)
    assert "V05" in codes  # the earlier quarter now carries five courses
    # a course moved into its prerequisite's quarter breaks V03; nothing else does
    assert ("V03" in codes) == (item.course in INTRO[1:])
    assert report.certificate is None
    if "V03" in codes:
        issue = next(i for i in report.issues if i.code == "V03" and i.level == "error")
        assert issue.course_ids == [item.course] and issue.fix_hints


@SETTINGS
@given(valid_plans(), st.data())
def test_adding_a_fifth_course(p: PlanState, data: st.DataObject) -> None:
    term = data.draw(st.sampled_from(T))
    extra = plan({term: ["FILL 14300"]}).items
    report = verify(p.model_copy(update={"items": [*p.items, *extra]}), RULES, CAT)
    assert error_codes(report) == {"V05"}
    (issue,) = [i for i in report.issues if i.code == "V05"]
    assert issue.term_ids == [term] and "500 units" in issue.message
    # in the fourth year the same quarter passes with a petition warning
    if T.index(term) >= 9:
        claimed = p.model_copy(
            update={"items": [*p.items, *extra], "overload_reasons": {term: "grad-need"}}
        )
        report = verify(claimed, RULES, CAT)
        assert report.status == "warnings" and report.certificate is not None
        assert check_certificate(claimed, RULES, CAT, report.certificate)


@SETTINGS
@given(valid_plans(), st.data())
def test_tampered_certificates_are_rejected(p: PlanState, data: st.DataObject) -> None:
    cert = verify(p, RULES, CAT).certificate
    assert cert is not None
    raw = cert.model_dump()
    kind = data.draw(st.sampled_from(["drop", "swap", "alien", "witness", "load", "hash", "rules"]))
    if kind == "drop":  # a node loses its assignment
        raw["assignments"].pop(data.draw(st.integers(0, len(raw["assignments"]) - 1)))
    elif kind == "swap":  # a course is claimed for a node it does not match
        entry = data.draw(st.sampled_from(raw["assignments"]))
        entry["courses"] = [*entry["courses"][1:], "FILL 10000"]
    elif kind == "alien":  # a course that is not in the plan
        raw["assignments"][0]["courses"] = ["FILL 14300"]
    elif kind == "witness":  # a prerequisite witness that proves nothing
        entry = data.draw(st.sampled_from(raw["prereq_witnesses"]))
        entry["by"] = data.draw(
            st.sampled_from([[], ["FILL 10000@2026-AU"], ["INTR 10100@2031-AU"]])
        )
    elif kind == "load":
        raw["loads"][data.draw(st.integers(0, 11))]["units"] += 100
    elif kind == "hash":
        raw["plan_hash"] = "sha256:" + "0" * 64
    else:
        raw["rules"].pop("core@2026-27")
    assert not check_certificate(p, RULES, CAT, Certificate.model_validate(raw))


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.tuples(
            st.sampled_from([*INTRO, *ELEC, *MINR, *ARTS, "LANG 10300", *FILL[:6]]),
            st.sampled_from(T[:6]),
        ),
        max_size=24,
    ),
    st.sampled_from([PROGRAMS, ["w-bs"], ["w-minor", "w-bs"], []]),
)
def test_arbitrary_plans_only_get_certificates_that_check(
    picks: list[tuple[str, str]], programs: list[str]
) -> None:
    items: dict[str, list[str]] = {}
    for code, term in picks:
        items.setdefault(term, []).append(code)
    p = plan(items, programs=programs)
    for options in (None, {"checks": ["V01", "V02", "V03", "V07"]}):
        from planner_core.models import VerifyOptions

        report = verify(p, RULES, CAT, VerifyOptions.model_validate(options) if options else None)
        assert (report.certificate is None) == (report.status == "errors")
        if report.certificate is not None:
            assert check_certificate(p, RULES, CAT, report.certificate)
