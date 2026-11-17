"""SelectorMatcher follows docs/CONTRACTS.md "Selector semantics" (no database needed)."""

from typing import Any

import pytest
from api.repo.catalog import (
    NotFoundError,
    SelectorMatcher,
    fill_targets,
    find_node,
    normalize_code,
)
from planner_core.models import Catalog, Course, CourseList, ProgramRules, Selector

SRC = {"url": "https://example.invalid/fake-catalog", "quote": "FAKE FIXTURE - not a real course"}

CATALOG = Catalog(
    catalog_year="2099-00",
    courses=[
        Course(code="TEST 10000", title="Intro"),
        Course(code="TEST 20100", title="Cross A"),
        Course(code="FAKE 20100", title="Cross B", tags=["writing"]),
        Course(code="TEST 29999", title="Edge", core_tags=["arts"]),
        Course(code="TEST 30000", title="Upper", tags=["ml"]),
        Course(code="OTHR 12000", title="Other", core_tags=["huma"]),
    ],
    crosslist_groups=[["FAKE 20100", "TEST 20100"]],
    course_lists=[
        CourseList(name="seqs", sublists=["seq-a", "seq-b"]),
        CourseList(name="seq-a", courses=["TEST 10000"]),
        CourseList(name="seq-b", courses=["FAKE 20100"], sublists=["seq-c"]),
        CourseList(name="seq-c", courses=["OTHR 12000"], sublists=["seqs"]),  # a cycle
    ],
)
CODES = sorted(c.code for c in CATALOG.courses)


def accepted(selector: dict[str, Any]) -> list[str]:
    matcher = SelectorMatcher(CATALOG)
    sel = Selector.model_validate(selector)
    return [code for code in CODES if matcher.matches(code, sel)]


def test_codes_match_by_crosslist_group() -> None:
    assert accepted({"codes": ["TEST 10000"]}) == ["TEST 10000"]
    assert accepted({"codes": ["FAKE 20100"]}) == ["FAKE 20100", "TEST 20100"]


def test_subject_and_inclusive_number_range() -> None:
    assert accepted({"subject": "OTHR"}) == ["OTHR 12000"]
    # FAKE 20100 matches through its partner TEST 20100.
    assert accepted({"subject": "TEST", "number_range": [20100, 29999]}) == [
        "FAKE 20100",
        "TEST 20100",
        "TEST 29999",
    ]
    assert accepted({"number_range": [30000, 30000]}) == ["TEST 30000"]


def test_tags_include_core_tags_with_prefix() -> None:
    assert accepted({"tags": ["core:arts"]}) == ["TEST 29999"]
    assert accepted({"tags": ["arts"]}) == []
    assert accepted({"tags": ["ml", "core:huma"]}) == ["OTHR 12000", "TEST 30000"]
    assert accepted({"tags": ["writing"]}) == ["FAKE 20100", "TEST 20100"]


def test_list_includes_sublists_recursively_and_survives_cycles() -> None:
    assert accepted({"list": "seq-a"}) == ["TEST 10000"]
    assert accepted({"list": "seqs"}) == ["FAKE 20100", "OTHR 12000", "TEST 10000", "TEST 20100"]
    assert accepted({"list": "seq-c"}) == accepted({"list": "seqs"})
    assert accepted({"list": "no-such-list"}) == []


def test_criteria_combine_with_and_union_is_or() -> None:
    assert accepted({"subject": "TEST", "tags": ["ml"]}) == ["TEST 30000"]
    assert accepted({"union": [{"subject": "OTHR"}, {"codes": ["TEST 30000"]}]}) == [
        "OTHR 12000",
        "TEST 30000",
    ]
    assert accepted({"subject": "TEST", "union": [{"list": "seq-a"}, {"tags": ["ml"]}]}) == [
        "TEST 10000",
        "TEST 30000",
    ]


def test_criteria_hold_for_one_member_of_the_group() -> None:
    # No single member is both TEST and tagged `writing` (the tag is on FAKE 20100).
    assert accepted({"subject": "TEST", "tags": ["writing"]}) == []


def test_exclude_works_on_crosslist_groups() -> None:
    assert accepted({"subject": "TEST", "exclude": ["FAKE 20100"]}) == [
        "TEST 10000",
        "TEST 29999",
        "TEST 30000",
    ]
    assert accepted({"union": [{"list": "seqs", "exclude": ["TEST 20100"]}]}) == [
        "OTHR 12000",
        "TEST 10000",
    ]


PROGRAM = ProgramRules.model_validate(
    {
        "id": "test-bs",
        "catalog_year": "2099-00",
        "rules": {
            "group": {
                "all": True,
                "children": [
                    {
                        "id": "intro",
                        "group": {
                            "all": True,
                            "children": [
                                {"slot": {"any_of": ["TEST 20100"]}},
                                {"slot": {"any_of": ["TEST 10000"]}},
                            ],
                        },
                    },
                    {
                        "id": "electives",
                        "label": "Electives",
                        "select": {
                            "count": 1,
                            "from": {"subject": "TEST", "exclude": ["TEST 30000"]},
                        },
                    },
                    {
                        "id": "core",
                        "bounded_parts": {
                            "total": {"courses": 2},
                            "parts": [
                                {
                                    "id": "arts",
                                    "label": "Arts",
                                    "from": {"tags": ["core:arts"]},
                                    "count": [0, 2],
                                },
                                {"id": "huma", "from": {"tags": ["core:huma"]}, "count": [0, 2]},
                            ],
                        },
                    },
                ],
            }
        },
    }
)


def filled_by(path: str) -> list[str]:
    matcher = SelectorMatcher(CATALOG)
    node = find_node(PROGRAM, path)
    return [code for code in CODES if matcher.fills(code, node)]


def test_fills_slots_selects_parts_and_containers() -> None:
    assert filled_by("test-bs/intro/1") == ["FAKE 20100", "TEST 20100"]
    assert filled_by("test-bs/electives") == [
        "FAKE 20100",
        "TEST 10000",
        "TEST 20100",
        "TEST 29999",
    ]
    assert filled_by("test-bs/core/arts") == ["TEST 29999"]
    assert filled_by("test-bs/core") == ["OTHR 12000", "TEST 29999"]
    assert filled_by("test-bs/intro") == ["FAKE 20100", "TEST 10000", "TEST 20100"]


def test_fill_targets_are_leaves_in_tree_order() -> None:
    assert [(path, node.label) for path, node in fill_targets(PROGRAM)] == [
        ("test-bs/intro/1", None),
        ("test-bs/intro/2", None),
        ("test-bs/electives", "Electives"),
        ("test-bs/core/arts", "Arts"),
        ("test-bs/core/huma", None),
    ]


def test_find_node_accepts_relative_paths_and_rejects_unknown() -> None:
    assert find_node(PROGRAM, "electives") is find_node(PROGRAM, "test-bs/electives")
    assert find_node(PROGRAM, "/test-bs/core/arts/").id == "arts"
    assert find_node(PROGRAM, "test-bs") is PROGRAM.rules
    for bad in ("nope", "test-bs/intro/3", "", "test-bs/core/nope"):
        with pytest.raises(NotFoundError, match="Unknown node"):
            find_node(PROGRAM, bad)


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("CMSC 14100", "CMSC 14100"),
        ("cmsc-14100", "CMSC 14100"),
        ("CMSC14100", "CMSC 14100"),
        (" math  20700 ", "MATH 20700"),
        ("CMSC+14100", "CMSC 14100"),
        ("CMSC 141", None),
        ("14100", None),
        ("C 14100", None),
    ],
)
def test_normalize_code(raw: str, code: str | None) -> None:
    assert normalize_code(raw) == code
