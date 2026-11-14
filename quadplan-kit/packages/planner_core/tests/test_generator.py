"""Deterministic plan generator (prompt 06) on a small made-up catalog."""

from typing import Any

import pytest
from planner_core import generator as gen
from planner_core.changes import apply_ops
from planner_core.goalcompile import compile_goals, term_label
from planner_core.index import Index
from planner_core.models import (
    AttributeValue,
    Catalog,
    CollegePolicy,
    Course,
    CourseList,
    CourseRelation,
    GenerateOptions,
    OfferingPattern,
    PlanState,
    ProgramRules,
    Report,
    Requisite,
    RuleSet,
    Section,
    Source,
)
from planner_core.preferences import default_preference, interest_match, preferences
from planner_core.terms import term_key

SRC = {"url": "https://example.invalid", "quote": "fake"}
YEAR = "2099-00"


def courses() -> list[Course]:
    out = [
        Course(code=f"TEST {n}", title=f"Test {n}")
        for n in (10000, 10100, 10200, 20000, 20100, 20200, 20300, 20400, 20500, 20600)
    ]
    out += [
        Course(code=f"GEN {n}", title=f"General {n}", tags=["ml"] if n == 10300 else [])
        for n in range(10000, 11000, 100)
    ]
    out += [Course(code="CORE 10000", title="Core A1"), Course(code="CORE 10100", title="Core A2")]
    out += [Course(code="CORE 11000", title="Core B1"), Course(code="CORE 11100", title="Core B2")]
    out += [
        Course(code="PLC 10000", title="Placed"),
        Course(code="STD 20000", title="Upper standing"),
    ]
    out += [Course(code="REP 10000", title="Workshop", repeatable=True)]
    out += [Course(code="ABR 20000", title="Abroad 1"), Course(code="ABR 20100", title="Abroad 2")]
    out += [Course(code="MED 10000", title="Premed chem")]
    return out


def catalog(**extra: Any) -> Catalog:
    return Catalog(
        catalog_year=YEAR,
        courses=courses(),
        course_lists=[
            CourseList(name="core-seqs", sublists=["core-a", "core-b"]),
            CourseList(name="core-a", courses=["CORE 10000", "CORE 10100"]),
            CourseList(name="core-b", courses=["CORE 11000", "CORE 11100"]),
        ],
        relations=[CourseRelation(a="TEST 20500", b="TEST 20600", kind="mutually_exclusive")],
        offerings=[
            OfferingPattern(course="TEST 20100", quarter=q, p_offered=p, method="catalog")
            for q, p in (("AU", 0.95), ("WI", 0.05), ("SP", 0.05))
        ],
        attributes=[
            AttributeValue(subject_id="TEST 20200", key="workload_hours", value=20, ci_high=25),
            AttributeValue(subject_id="TEST 20200", key="difficulty", value=4.5),
            AttributeValue(subject_id="TEST 20300", key="difficulty", value=4.6),
            AttributeValue(subject_id="TEST 20200", key="grading_strictness", value=4.5),
            AttributeValue(subject_id="TEST 20300", key="grading_strictness", value=4.5),
            AttributeValue(subject_id="GEN 10200", key="recommend_rate", value=90),
        ],
        **extra,
    )


def requisites() -> list[Requisite]:
    return [
        Requisite(course="TEST 10100", prereq="TEST 10000"),
        Requisite(
            course="TEST 10200", prereq={"all": ["TEST 10100", {"any": ["GEN 10000", "GEN 10100"]}]}
        ),
        Requisite(course="TEST 20000", prereq={"all": ["TEST 10200", {"consent": "instructor"}]}),
        Requisite(course="TEST 20400", coreq={"concurrent": "TEST 20300"}),
        Requisite(
            course="TEST 20500", prereq={"n_of": 1, "of": ["TEST 10100", {"program": "nothing-*"}]}
        ),
        Requisite(course="PLC 10000", prereq={"placement": "PLC 10000"}),
        Requisite(course="STD 20000", prereq={"standing": "fourth-year"}),
        Requisite(course="GEN 10900", restrictions={"program": "test-*"}),
    ]


def program(pid: str, rules: dict[str, Any], kind: str, **policy: Any) -> ProgramRules:
    return ProgramRules.model_validate(
        {"id": pid, "catalog_year": YEAR, "type": kind, "rules": rules, "policy": policy}
    )


CORE = program(
    "core",
    {
        "bounded_parts": {
            "total": {"courses": 2},
            "parts": [
                {"id": "seq", "from": {"list": "core-seqs"}, "count": [2, 2], "same_sequence": True}
            ],
        }
    },
    "core",
)
MAJOR = program(
    "test-bs",
    {
        "group": {
            "all": True,
            "children": [
                {
                    "id": "intro",
                    "group": {
                        "all": True,
                        "children": [
                            {"slot": {"any_of": ["TEST 10000"]}},
                            {"slot": {"any_of": ["TEST 10100"]}},
                        ],
                    },
                },
                {
                    "id": "upper",
                    "select": {
                        "count": 2,
                        "from": {"subject": "TEST", "number_range": [20000, 29999]},
                    },
                    "constraints": {
                        "in_order": True,
                        "max_from": {"selector": {"codes": ["TEST 20000"]}, "n": 1},
                    },
                },
            ],
        }
    },
    "major",
    share=[{"with": "type:minor", "max": 0}],
    residency={"min_fraction": 0.5},
)
MINOR = program("gen-minor", {"select": {"count": 1, "from": {"subject": "GEN"}}}, "minor")
ABROAD = program(
    "abroad", {"select": {"count": 2, "from": {"subject": "ABR"}}}, "study_abroad_block"
)
BXMS = program(
    "test-bxms",
    {"slot": {"any_of": ["TEST 20600"]}},
    "bxms",
    timing={"apply_by": "Y2-WI", "apply_requires": ["TEST 10200"]},
)


def college(**update: Any) -> CollegePolicy:
    values: dict[str, Any] = {
        "catalog_year": YEAR,
        "total_units": 800,
        "units_by_enrollment": 700,
        "full_time_min_units": 200,
        "full_time_max_units": 300,
        "overload_units": 400,
        "overload_reasons": [{"id": "thesis", "label": "Thesis year", "year": 2}],
        "core_complete_by": "Y1-SP",
        "max_quarters": 6,
    }
    values.update(update)
    values["sources"] = {k: SRC for k in values if k not in ("catalog_year", "overload_reasons")}
    return CollegePolicy.model_validate(values)


def ruleset(*extra: ProgramRules, **policy: Any) -> RuleSet:
    return RuleSet(
        catalog_year=YEAR,
        programs=[CORE, MAJOR, MINOR, ABROAD, BXMS, *extra],
        college=college(**policy),
        requisites=requisites(),
    )


def plan(*programs: str, items: list[dict[str, Any]] | None = None, **update: Any) -> PlanState:
    data: dict[str, Any] = {
        "catalog_year": YEAR,
        "entry_term": "2099-AU",
        "entry_year_level": 3,  # two years left: six quarters
        "programs": [{"program_id": p} for p in programs or ("core", "test-bs")],
        "items": items or [],
    }
    data.update(update)
    return PlanState.model_validate(data)


def run(p: PlanState, rules: RuleSet | None = None, cat: Catalog | None = None, **opts: Any):  # type: ignore[no-untyped-def]
    options = GenerateOptions(**{"time_limit_s": 10, **opts})
    return gen.generate(p, rules or ruleset(), cat or catalog(), options)


def placed(result: Any, n: int = 0) -> dict[str, str]:
    return {i.course: i.term for i in result.variants[n].plan.items if i.course}


# ------------------------------------------------------------------------- happy paths


def test_generates_verified_variants_that_replay() -> None:
    p = plan()
    result = run(p, variants=3)
    assert result.infeasible is None and result.alerts == []
    assert 1 <= len(result.variants) <= 3
    for v in result.variants:
        assert v.report.certificate is not None and v.report.status != "errors"
        replay = apply_ops(p, v.ops)
        assert sorted((i.course, i.term) for i in replay.items) == sorted(
            (i.course, i.term) for i in v.plan.items
        )
        assert v.metrics["courses_added"] == len(v.ops)
    first = placed(result)
    assert (
        first["TEST 10000"] < first["TEST 10100"]
        or first["TEST 10000"][:4] < first["TEST 10100"][:4]
    )
    for later in result.variants[1:]:
        a, b = (
            set(placed(result).items()),
            set({i.course: i.term for i in later.plan.items if i.course}.items()),
        )
        assert len(a ^ b) >= gen.MIN_DIFFERENCE


def test_keeps_fixed_courses_and_reuses_the_students_own() -> None:
    items = [
        {"id": "1", "course": "TEST 10000", "term": "2099-AU", "status": "completed", "grade": "A"},
        {"id": "2", "course": "TEST 10100", "term": "2100-WI", "locked": True},
        {"id": "3", "course": "GEN 10000", "term": "2100-SP"},
        {"id": "4", "course": "GEN 10000", "term": "2100-SP"},  # duplicate: dropped
        {"id": "5", "slot_ref": "core/seq", "term": "2100-SP"},
        {"id": "6", "course": "TEST 20200", "term": "2101-SU"},  # Summer is never planned
    ]
    p = plan(items=items)
    result = run(p)
    v = result.variants[0]
    by_id = {i.id: i for i in v.plan.items if i.id}
    assert by_id["1"].term == "2099-AU" and by_id["2"].term == "2100-WI" and "6" in by_id
    assert "5" not in by_id and "4" not in by_id
    assert any(op.op == "remove" for op in v.ops)
    replay = apply_ops(p, v.ops)
    assert sorted((i.course, i.term) for i in replay.items) == sorted(
        (i.course, i.term) for i in v.plan.items
    )


def test_scopes_and_moves() -> None:
    items = [{"id": "9", "course": "TEST 10000", "term": "2101-SP"}]
    result = run(plan(items=items), scope="remaining", today_term="2100-WI", load=-1)
    v = result.variants[0]
    assert all(
        term_key(i.term) >= term_key("2100-WI") for i in v.plan.items if i.course and i.id is None
    )
    selected = run(plan(), scope="selected", selected_terms=[])
    assert selected.infeasible is not None and "no quarters" in selected.infeasible.message
    heavy = run(plan(), load=1, per_term_load={"2100-WI": 1.0, "2100-SP": -1.0})
    assert heavy.variants


def test_offering_placement_standing_and_program_atoms() -> None:
    p = plan(
        placements=["PLC 10000"],
        goals=[
            {
                "id": "g",
                "type": "premed",
                "courses": ["PLC 10000", "STD 20000", "TEST 20100", "GEN 10900"],
                "complete_by": "Y2-SP",
            },
        ],
    )
    result = run(p)
    got = placed(result)
    assert got["TEST 20100"].endswith("AU")  # only usually offered in Autumn
    assert term_key(got["STD 20000"]) >= term_key("2100-AU")  # fourth-year standing
    rare = run(p, allow_rarely_offered=["TEST 20100"])
    assert rare.variants
    no_placement = run(plan(goals=p.goals))
    assert no_placement.infeasible is not None


def test_posted_schedule_and_relations() -> None:
    cat = catalog(sections=[Section(term="2099-AU", course="GEN 10500", section_no="1")])
    items = [{"id": "1", "course": "TEST 20600", "term": "2099-AU", "status": "completed"}]
    result = run(plan(items=items), cat=cat)
    got = placed(result)
    assert all(
        term != "2099-AU" or code == "GEN 10500" or code == "TEST 20600"
        for code, term in got.items()
    )
    assert "TEST 20500" not in got  # mutually exclusive with the completed TEST 20600


def test_every_goal_type_compiles_and_generates() -> None:
    goals = [
        {"id": "load", "type": "course_load", "min_courses": 2, "max_courses": 3},
        {
            "id": "light",
            "type": "light_quarter",
            "scope": "term",
            "term": "2100-SP",
            "max_courses": 3,
        },
        {"id": "grad", "type": "graduate_by", "by_term": "Y2-SP"},
        {"id": "work", "type": "workload_hours", "max_hours": 30, "hard": True},
        {
            "id": "work2",
            "type": "workload_hours",
            "max_hours": 15,
            "aggregate": "career_average",
            "strict": True,
        },
        {"id": "hard", "type": "difficulty_cap", "max_very_hard": 1, "hard": True},
        {"id": "hard2", "type": "difficulty_cap", "max_index": 6},
        {"id": "chal", "type": "challenge", "min_index": 3},
        {"id": "gpa", "type": "protect_gpa"},
        {"id": "int", "type": "interest", "tags": ["ml"]},
        {
            "id": "lang",
            "type": "language",
            "language": "Test",
            "level": "competence",
            "by_term": "Y2-WI",
            "courses": ["GEN 10500"],
        },
        {"id": "bx", "type": "bxms", "program_id": "test-bxms", "apply_by": "Y2-WI"},
    ]
    p = plan(goals=goals)
    specs = compile_goals(p.goals, p, ruleset(), Index(catalog(), ruleset()))
    assert {s.mode for s in specs} == {"hard", "penalty", "reward", "precedence"}
    assert all(s.label for s in specs)
    result = run(p)
    assert result.variants, result.infeasible
    got = placed(result)
    assert "GEN 10300" in got  # the interest goal rewards the course tagged "ml"
    assert term_key(got["TEST 10200"]) < term_key("2101-WI")  # bxms application prerequisite
    report = result.variants[0].report
    assert any("no workload" in a for a in report.assumptions)


def test_study_abroad_block_is_pinned() -> None:
    goals = [{"id": "ab", "type": "study_abroad", "program_id": "abroad", "abroad_term": "Y2-WI"}]
    result = run(plan("core", "test-bs", "abroad", goals=goals))
    got = placed(result)
    assert got["ABR 20000"] == got["ABR 20100"] == "2101-WI"
    assert sorted(c for c, t in got.items() if t == "2101-WI") == ["ABR 20000", "ABR 20100"]
    missing = run(
        plan(
            goals=[
                {"id": "x", "type": "study_abroad", "program_id": "nowhere", "abroad_term": "Y2-WI"}
            ]
        )
    )
    assert missing.infeasible is not None
    occupied = run(
        plan(
            "core",
            "test-bs",
            "abroad",
            goals=goals,
            items=[{"course": "GEN 10100", "term": "2101-WI", "status": "completed"}],
        )
    )
    assert occupied.infeasible is not None


def test_repeatable_and_overload() -> None:
    rep = program("rep", {"select": {"count": 2, "from": {"codes": ["REP 10000"]}}}, "minor")
    result = run(plan("core", "test-bs", "rep"), rules=ruleset(rep))
    assert sum(1 for i in result.variants[0].plan.items if i.course == "REP 10000") == 2
    over = plan(overload_reasons={"2100-AU": "thesis"})
    assert run(over, allow_overload=True).variants


# ------------------------------------------------------------------------- explanations


def test_missing_core_unknown_program_and_bad_quarters() -> None:
    no_core = run(plan("test-bs"))
    assert no_core.infeasible is not None and "Core" in no_core.infeasible.message
    unknown = run(plan("core", "nope"))
    assert unknown.infeasible is not None and "nope" in unknown.infeasible.message
    half = [{"course": "GEN 10000", "term": "2099-AU"}]
    bad = run(plan(items=half), scope="selected", selected_terms=["2100-WI"])
    assert bad.infeasible is not None
    assert any(c.kind == "load" for c in bad.infeasible.conflicts)


def test_graduating_too_early_names_the_shortfall() -> None:
    goals = [{"id": "g", "type": "graduate_by", "by_term": "Y1-WI", "hard": True}]
    result = run(plan(goals=goals))
    assert result.infeasible is not None
    assert result.infeasible.message.startswith(f"Graduating by {term_label('2100-WI')} needs ")
    assert "more courses than your remaining quarters allow" in result.infeasible.message


def test_conflicting_limits_are_listed() -> None:
    goals = [{"id": "few", "type": "course_load", "max_courses": 1}]
    result = run(plan(goals=goals), max_courses_per_term=1)
    assert result.infeasible is not None
    assert result.infeasible.conflicts
    ids = {c.id for c in result.infeasible.conflicts}
    assert "graduation" in ids and ids & {"goal:few", "courses_per_term"}
    assert "To graduate you still need" in result.infeasible.message


def test_unmet_requirement_mentions_placement() -> None:
    placed_only = program("plc", {"slot": {"any_of": ["PLC 10000"]}}, "minor")
    result = run(plan("core", "test-bs", "plc"), rules=ruleset(placed_only))
    assert result.infeasible is not None
    assert "placement result" in result.infeasible.message


def test_rejected_variants_raise_an_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(p: PlanState, *_: Any) -> tuple[Report, list[str]]:
        return Report(status="errors", plan_hash="x", core_version="x"), ["boom"]

    monkeypatch.setattr(gen, "verify_checked", broken)
    result = run(plan())
    assert result.variants == [] and result.alerts and "ALERT" in result.alerts[0]
    assert result.infeasible is not None and "bug" in result.infeasible.message


def test_without_college_policy() -> None:
    rules = RuleSet(catalog_year=YEAR, programs=[MAJOR], requisites=requisites())
    result = run(plan("test-bs"), rules=rules, max_courses_per_term=2)
    assert result.variants


# ------------------------------------------------------------------------- preferences


def test_default_preferences_order() -> None:
    idx = Index(catalog(), ruleset())
    assert interest_match(idx, "GEN 10300", ["ML"]) and not interest_match(idx, "GEN 10300", [" "])
    assert interest_match(idx, "TEST 10000", ["test"])
    assert default_preference(idx, "GEN 10300", ["ml"]) > default_preference(
        idx, "GEN 10200", ["ml"]
    )
    assert default_preference(idx, "GEN 10200", []) > default_preference(idx, "GEN 10100", [])
    assert default_preference(idx, "GEN 10100", []) > default_preference(idx, "TEST 20000", [])
    prefs = preferences(idx, ["GEN 10100", "GEN 10200"], [], {"GEN 10100": 100})
    assert prefs["GEN 10100"] == 20000 and prefs["GEN 10200"] < 10000


def test_horizon_and_open_terms() -> None:
    p = plan(items=[{"course": "GEN 10000", "term": "2101-SU"}], entry_year_level=1)
    terms = gen.horizon(p)
    assert (
        terms[0] == "2099-AU"
        and "2101-SU" in terms
        and len([t for t in terms if not t.endswith("SU")]) == 12
    )
    assert "2101-SU" not in gen.open_terms(p, GenerateOptions())
    assert Source.model_validate(SRC)
