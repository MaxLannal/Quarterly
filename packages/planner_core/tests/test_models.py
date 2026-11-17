"""Contract tests: the spec's YAML examples parse and round-trip; invalid input is rejected."""

from typing import Any

import pytest
import yaml
from planner_core.dsl import expr_courses, expr_to_text, iter_parts, node_paths
from planner_core.models import (
    BoundedPartsNode,
    Certificate,
    ChangeOp,
    ChangeSet,
    CollegePolicy,
    Course,
    Expr,
    Goal,
    GroupNode,
    Node,
    PlanItem,
    PlanState,
    Policy,
    ProgramRules,
    Report,
    SelectNode,
    SlotNode,
    Source,
)
from pydantic import TypeAdapter, ValidationError

NODE = TypeAdapter(Node)
GOAL = TypeAdapter(Goal)
OP = TypeAdapter(ChangeOp)

# --- Verbatim examples from docs/SPEC.md "Requirements DSL" ---------------------------------

CORE_HCA = """
id: core-hca
label: Humanities, Civilization Studies, and the Arts
bounded_parts:
  total: {courses: 6}
  parts:
    - {id: huma, from: {list: core-huma-sequences}, count: [2, 3], same_sequence: true}
    - {id: civ,  from: {list: core-civ-sequences},  count: [2, 3], same_sequence: true}
    - {id: arts, from: {list: core-arts},           count: [1, 2]}
constraints: {no_pass_fail: true}
source: {snapshot_id: snap_core_2026, quote: "must be taken for a total of 6 courses"}
"""

CMSC_BS = """
id: cmsc-bs
catalog_year: "2026-27"
rules:
  group:
    all: true
    children:
      - id: intro
        group:
          all: true
          children:
            - {slot: {any_of: ["CMSC 14100"]}}
            - {slot: {any_of: ["CMSC 14200"]}}
      - id: electives            # ILLUSTRATIVE
        select:
          count: 4
          from: {subject: CMSC, number_range: [20000, 29999], exclude: ["CMSC 29700"]}
        constraints: {min_grade: "C-", no_pass_fail: true}
policy:
  share:
    - {with: "type:minor", max: 0}
"""

CERTIFICATE = """
{
  "plan_hash": "sha256:abc",
  "rules": {"cmsc-bs@2026-27": "sha256:def", "core@2026-27": "sha256:123"},
  "assignments": [{"node": "cmsc-bs/intro/1", "courses": ["CMSC 14100"]}],
  "prereq_witnesses": [{"course": "CMSC 14200", "term": "2027-WI", "by": ["CMSC 14100@2026-AU"]}],
  "loads": [{"term": "2026-AU", "units": 400}],
  "goals": [{"goal": "g3", "value": 41.5, "limit": 45, "pass": true}]
}
"""

ATOMS = [
    ({"course": "CMSC 14200", "min_grade": "C-"}, "CMSC 14200 (grade C- or higher)"),
    ({"concurrent": "MATH 20300"}, "MATH 20300 (may be taken concurrently)"),
    ({"placement": "MATH 15100"}, "placement into MATH 15100"),
    ({"standing": "third-year"}, "third-year standing"),
    ({"program": "cmsc-*"}, "enrolled in cmsc-*"),
    ({"consent": "instructor"}, "consent of instructor"),
]


def roundtrip(adapter: TypeAdapter[Any], data: Any) -> Any:
    first = adapter.validate_python(data)
    dumped = adapter.dump_python(first, mode="json", by_alias=True)
    second = adapter.validate_python(dumped)
    assert second == first
    assert adapter.dump_python(second, mode="json", by_alias=True) == dumped
    return first


def test_core_hca_example() -> None:
    node = roundtrip(NODE, yaml.safe_load(CORE_HCA))
    assert isinstance(node, BoundedPartsNode)
    assert node.total.courses == 6
    assert [p.id for p in node.parts] == ["huma", "civ", "arts"]
    assert node.parts[0].constraints.same_sequence is True
    assert node.parts[0].from_.list_ == "core-huma-sequences"
    assert node.parts[2].count == (1, 2)
    assert node.constraints.no_pass_fail is True
    assert node.source == Source(
        snapshot_id="snap_core_2026", quote="must be taken for a total of 6 courses"
    )


def test_cmsc_bs_example_paths_and_roundtrip() -> None:
    program = roundtrip(TypeAdapter(ProgramRules), yaml.safe_load(CMSC_BS))
    assert node_paths(program) == [
        "cmsc-bs",
        "cmsc-bs/intro",
        "cmsc-bs/intro/1",
        "cmsc-bs/intro/2",
        "cmsc-bs/electives",
    ]
    electives = program.rules.children[1]  # type: ignore[union-attr]
    assert isinstance(electives, SelectNode)
    assert electives.from_.number_range == (20000, 29999)
    assert electives.constraints.min_grade == "C-"
    assert program.policy.share[0].with_ == "type:minor"
    dumped = program.model_dump(mode="json")
    assert dumped["policy"]["share"][0] == {
        "with": "type:minor",
        "max": 0,
        "except": [],
        "source": None,
    }
    assert dumped["rules"]["children"][1]["from"]["exclude"] == ["CMSC 29700"]


def test_certificate_example_roundtrip() -> None:
    cert = roundtrip(TypeAdapter(Certificate), yaml.safe_load(CERTIFICATE))
    assert cert.goals[0].pass_ is True
    assert cert.model_dump()["goals"][0]["pass"] is True


@pytest.mark.parametrize(("shorthand", "text"), ATOMS)
def test_atom_shorthand(shorthand: dict[str, str], text: str) -> None:
    expr = roundtrip(TypeAdapter(Expr), shorthand)
    assert expr.op == "atom"
    assert expr_to_text(expr) == text


def test_combinators_and_human_form() -> None:
    expr = Expr.model_validate({"all": ["CMSC 14200", {"any": ["MATH 15900", "MATH 16300"]}]})
    assert expr_to_text(expr) == "CMSC 14200 and (MATH 15900 or MATH 16300)"
    assert expr_courses(expr) == {"CMSC 14200", "MATH 15900", "MATH 16300"}
    n_of = Expr.model_validate(
        {"n_of": 2, "of": ["MATH 15100", "MATH 15200", {"consent": "instructor"}]}
    )
    assert expr_to_text(n_of) == "2 of (MATH 15100, MATH 15200, consent of instructor)"
    assert expr_courses(n_of) == {"MATH 15100", "MATH 15200"}
    nested = Expr.model_validate(
        {"any": [{"all": ["MATH 15100", "MATH 15200"]}, n_of.model_dump()]}
    )
    assert expr_to_text(nested).startswith("(MATH 15100 and MATH 15200) or 2 of (")
    roundtrip(TypeAdapter(Expr), nested.model_dump())


@pytest.mark.parametrize(
    "bad",
    [
        {"course": "cmsc 141"},
        {"standing": "senior"},
        {"placement": "MATH 15100", "min_grade": "C"},
        {"all": []},
        {"all": ["CMSC 14100"], "any": ["CMSC 14200"]},
        {"n_of": 3, "of": ["CMSC 14100", "CMSC 14200"]},
        {"n_of": 1},
        {"course": "CMSC 14100", "extra": 1},
        {"op": "atom"},
        {"op": "all", "n": 2, "children": [{"course": "CMSC 14100"}]},
        {"mystery": 1},
        42,
    ],
)
def test_bad_expressions_rejected(bad: Any) -> None:
    with pytest.raises(ValidationError):
        Expr.model_validate(bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"slot": {"any_of": []}},
        {"select": {"count": 2, "units": 200, "from": {"subject": "CMSC"}}},
        {"select": {"from": {"subject": "CMSC"}}},
        {"select": {"count": 2, "from": {}}},
        {"select": {"count": 2, "from": {"subject": "CMSC", "number_range": [3, 1]}}},
        {"group": {"children": [{"slot": {"any_of": ["CMSC 14100"]}}]}},
        {"group": {"all": True, "n_of": 1, "children": [{"slot": {"any_of": ["CMSC 14100"]}}]}},
        {"group": {"n_of": 2, "children": [{"slot": {"any_of": ["CMSC 14100"]}}]}},
        {
            "group": {
                "all": True,
                "children": [
                    {"id": "a", "slot": {"any_of": ["CMSC 14100"]}},
                    {"id": "a", "slot": {"any_of": ["CMSC 14200"]}},
                ],
            }
        },
        {
            "bounded_parts": {
                "total": {"courses": 9},
                "parts": [{"id": "x", "from": {"list": "l"}, "count": [1, 2]}],
            }
        },
        {
            "bounded_parts": {
                "total": {"courses": 2},
                "parts": [{"id": "x", "from": {"list": "l"}, "count": [3, 2]}],
            }
        },
        {
            "bounded_parts": {
                "total": {},
                "parts": [{"id": "x", "from": {"list": "l"}, "count": [1, 2]}],
            }
        },
        {
            "bounded_parts": {
                "total": {"courses": 2},
                "parts": [
                    {"id": "x", "from": {"list": "l"}, "count": [1, 1]},
                    {"id": "x", "from": {"list": "m"}, "count": [1, 1]},
                ],
            }
        },
        {"slot": {"any_of": ["CMSC 14100"]}, "select": {"count": 1, "from": {"subject": "CMSC"}}},
        {"slot": ["CMSC 14100"]},
        {"id": "x", "slot": {"id": "y", "any_of": ["CMSC 14100"]}},
        {"slot": {"any_of": ["CMSC 14100"]}, "source": {"quote": "no location"}},
    ],
)
def test_bad_nodes_rejected(bad: Any) -> None:
    with pytest.raises(ValidationError):
        NODE.validate_python(bad)


def test_node_variants_and_constraints() -> None:
    node = NODE.validate_python(
        {
            "id": "root",
            "group": {
                "n_of": 1,
                "children": [
                    {"slot": {"any_of": ["MATH 20700"]}},
                    {
                        "id": "units",
                        "select": {
                            "units": 300,
                            "from": {"union": [{"tags": ["core:arts"]}, {"codes": ["ARTH 10100"]}]},
                        },
                        "constraints": {
                            "max_from": {"selector": {"subject": "ARTV"}, "n": 1},
                            "distinct_subjects": 2,
                        },
                    },
                ],
            },
        }
    )
    assert isinstance(node, GroupNode)
    first, second = node.children
    assert isinstance(first, SlotNode) and first.id == "1"
    assert isinstance(second, SelectNode) and second.units == 300
    assert second.constraints.max_from[0].n == 1
    roundtrip(NODE, node.model_dump(mode="json"))
    program = ProgramRules.model_validate(
        {"id": "p", "catalog_year": "2026-27", "rules": CORE_HCA_NODE()}
    )
    assert [p for p, _ in iter_parts(program)] == ["p/huma", "p/civ", "p/arts"]


def CORE_HCA_NODE() -> Any:
    return yaml.safe_load(CORE_HCA)


def test_course_properties() -> None:
    course = Course(code="MATH 20700", title="Honors Analysis in Rn I")
    assert (course.subject, course.number, course.units) == ("MATH", 20700, 100)


def test_college_policy_values_need_sources() -> None:
    with pytest.raises(ValidationError):
        CollegePolicy.model_validate({"catalog_year": "2026-27", "total_units": 4200})
    policy = CollegePolicy.model_validate(
        {
            "catalog_year": "2026-27",
            "total_units": 4200,
            "sources": {"total_units": {"url": "https://example.edu", "quote": "4200 units"}},
        }
    )
    assert policy.total_units == 4200


GOALS: list[dict[str, Any]] = [
    {
        "id": "g1",
        "type": "course_load",
        "scope": "term",
        "term": "2029-AU",
        "max_courses": 3,
        "hard": True,
    },
    {"id": "g2", "type": "workload_hours", "max_hours": 45, "aggregate": "per_term"},
    {"id": "g3", "type": "difficulty_cap", "max_very_hard": 1, "very_hard_threshold": 4.5},
    {"id": "g4", "type": "challenge", "min_index": 10},
    {"id": "g5", "type": "protect_gpa", "strictness_threshold": 4},
    {"id": "g6", "type": "graduate_by", "by_term": "Y4-SP"},
    {"id": "g7", "type": "study_abroad", "program_id": "paris-civ", "abroad_term": "Y2-SP"},
    {"id": "g8", "type": "bxms", "program_id": "cmsc-bxms", "apply_by": "Y3-WI"},
    {"id": "g9", "type": "premed", "list": "premed-core", "complete_by": "Y3-SP"},
    {"id": "g10", "type": "interest", "tags": ["ML"], "min_share": 0.5},
    {"id": "g11", "type": "light_quarter", "scope": "term", "term": "2027-WI", "max_courses": 2},
    {
        "id": "g12",
        "type": "language",
        "language": "Chinese",
        "level": "competence",
        "by_term": "Y2-SP",
    },
]


@pytest.mark.parametrize("goal", GOALS, ids=lambda g: g["type"])
def test_every_goal_type(goal: dict[str, Any]) -> None:
    parsed = roundtrip(GOAL, goal)
    assert parsed.type == goal["type"]


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "g", "type": "course_load"},
        {"id": "g", "type": "difficulty_cap"},
        {"id": "g", "type": "premed", "complete_by": "Y3-SP"},
        {"id": "g", "type": "light_quarter", "scope": "career", "max_courses": 2},
    ],
)
def test_goal_required_parameters(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GOAL.validate_python(bad)


def test_spec_policy_examples_roundtrip() -> None:
    policy = roundtrip(
        TypeAdapter(Policy),
        {
            "share": [
                {"with": "type:minor", "max": 0},
                {"with": "core", "max": 0, "except": ["language"]},
            ]
        },
    )
    assert policy.share[1].except_ == ["language"]


def test_goal_scope_must_match_term() -> None:
    with pytest.raises(ValidationError):
        GOAL.validate_python(
            {"id": "g", "type": "light_quarter", "max_courses": 2, "scope": "term"}
        )
    with pytest.raises(ValidationError):
        GOAL.validate_python({"id": "g", "type": "challenge", "min_index": 1, "term": "2027-WI"})


def test_plan_state_and_items() -> None:
    plan = PlanState.model_validate(
        {
            "catalog_year": "2026-27",
            "entry_term": "2026-AU",
            "items": [
                {"course": "CMSC 14100", "term": "2026-AU", "status": "completed", "grade": "A"},
                {"slot_ref": "core/hca/huma", "term": "2026-AU"},
            ],
            "credits": [
                {"kind": "AP", "label": "AP Calculus BC", "maps_to": "MATH 15100", "units": 100}
            ],
            "programs": [{"program_id": "cmsc-bs"}],
            "goals": GOALS[:2],
            "placements": ["MATH 15100"],
            "overload_reasons": {"2028-AU": "reading-research"},
        }
    )
    roundtrip(TypeAdapter(PlanState), plan.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        PlanItem.model_validate({"term": "2026-AU"})
    with pytest.raises(ValidationError):
        PlanItem.model_validate({"course": "CMSC 14100", "slot_ref": "x", "term": "2026-AU"})
    with pytest.raises(ValidationError):
        PlanItem.model_validate({"course": "CMSC 14100", "term": "2026-FA"})


def test_change_ops_and_change_set() -> None:
    ops = [
        {"op": "add", "course": "MATH 20700", "term": "2027-AU"},
        {"op": "move", "course": "CMSC 14200", "to_term": "2027-SP"},
        {"op": "remove", "slot_ref": "core/hca/arts"},
        {"op": "lock", "item_id": "17"},
        {"op": "unlock", "course": "CMSC 14100", "term": "2026-AU"},
    ]
    parsed = [roundtrip(OP, op) for op in ops]
    assert [p.op for p in parsed] == ["add", "move", "remove", "lock", "unlock"]
    change_set = ChangeSet.model_validate(
        {"origin": "chat", "ops": ops, "base_plan_hash": "sha256:x"}
    )
    assert change_set.status == "proposed"
    with pytest.raises(ValidationError):
        OP.validate_python({"op": "move", "to_term": "2027-SP"})
    with pytest.raises(ValidationError):
        OP.validate_python({"op": "add", "term": "2027-SP"})
    with pytest.raises(ValidationError):
        ChangeSet.model_validate({"origin": "chat", "ops": [], "base_plan_hash": "sha256:x"})


def test_report_shape() -> None:
    report = Report.model_validate(
        {
            "status": "errors",
            "plan_hash": "sha256:x",
            "core_version": "planner_core-0.1.0",
            "issues": [
                {
                    "code": "V03",
                    "level": "error",
                    "message": "CMSC 14200 needs CMSC 14100 in an earlier term",
                    "course_ids": ["CMSC 14200"],
                    "term_ids": ["2026-AU"],
                    "fix_hints": ["Move CMSC 14200 to 2027-WI or later"],
                }
            ],
            "progress": [
                {
                    "program_id": "cmsc-bs",
                    "node_id": "cmsc-bs/intro",
                    "satisfied": False,
                    "have": 1,
                    "need": 2,
                }
            ],
        }
    )
    roundtrip(TypeAdapter(Report), report.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        Report.model_validate(
            {
                "status": "errors",
                "plan_hash": "x",
                "core_version": "y",
                "issues": [{"code": "V13", "level": "error", "message": "m"}],
            }
        )
