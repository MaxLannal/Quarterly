"""Node-level agreement and validators (a)-(g)."""

from __future__ import annotations

import copy
from typing import Any

from ingest_rules import RULES, URL, catalog, fake_page, rules
from planner_core.models import ProgramRules
from worker.ingest import courseleaf
from worker.ingest.compare import count_nodes, node_agreement
from worker.ingest.golden import GoldenOutcome
from worker.ingest.validators import (
    check_agreement,
    check_backtranslation,
    check_golden,
    check_quotes,
    check_references,
    check_schema,
    check_size,
    min_courses,
)


def edited(fn: Any) -> ProgramRules:
    data = copy.deepcopy(RULES)
    fn(data)
    return ProgramRules.model_validate(data)


def children(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data["rules"]["group"]["children"]  # type: ignore[no-any-return]


# ----------------------------------------------------------------------- agreement


def test_identical_trees_agree_on_every_node() -> None:
    a = node_agreement(rules(), rules())
    assert a.identical and a.total == count_nodes(rules()) == 5 and a.rate == 1.0


def test_labels_quotes_and_code_order_do_not_count() -> None:
    def change(d: dict[str, Any]) -> None:
        d["rules"]["label"] = "Another label"
        intro = children(d)[0]["group"]["children"][0]
        intro["slot"]["any_of"] = ["FSCI 10150", "FSCI 10100"]
        intro["source"] = {"url": URL, "quote": "something else"}

    assert node_agreement(rules(), edited(change)).identical


def test_a_changed_node_is_one_disagreement() -> None:
    other = edited(lambda d: children(d)[1].update({"constraints": {"no_pass_fail": False}}))
    a = node_agreement(rules(), other)
    assert (a.agreed, a.total) == (4, 5)
    (d,) = a.disagreements
    assert d.path == "fsci-bs/methods" and d.kind == "different"


def test_renamed_children_still_line_up() -> None:
    def rename(d: dict[str, Any]) -> None:
        children(d)[0]["id"] = "introductory"
        children(d)[1]["id"] = "bs-methods"

    assert node_agreement(rules(), edited(rename)).identical


def test_missing_and_extra_subtrees_count_every_node() -> None:
    a = node_agreement(rules(), edited(lambda d: children(d).pop(0)))
    assert a.total == 5 and a.agreed == 2
    assert {d.kind for d in a.disagreements} == {"missing"}
    b = node_agreement(edited(lambda d: children(d).pop(0)), rules())
    assert b.total == 5 and {d.kind for d in b.disagreements} == {"extra"}


def test_policy_is_one_node() -> None:
    share = {"share": [{"with": "type:minor", "max": 0, "source": {"url": URL, "quote": "q"}}]}
    with_policy = edited(lambda d: d.update({"policy": share}))
    a = node_agreement(with_policy, rules())
    assert a.total == 6 and a.disagreements[0].path == "fsci-bs/policy"
    assert node_agreement(with_policy, with_policy).identical


# ---------------------------------------------------------------------- validators


def test_schema_needs_a_source_on_every_node() -> None:
    parsed, check = check_schema(RULES)
    assert parsed is not None and check.ok
    no_source = copy.deepcopy(RULES)
    del children(no_source)[1]["source"]
    parsed, check = check_schema(no_source)
    assert parsed is not None and not check.ok
    assert check.problems == ["fsci-bs/methods: no source quote"]
    broken, check = check_schema({"id": "fsci-bs"})
    assert broken is None and not check.ok and check.id == "a"


def test_references_must_exist() -> None:
    assert check_references(rules(), catalog()).ok
    bad = edited(lambda d: children(d)[1]["slot"].update({"any_of": ["FSCI 99999"]}))
    listed = edited(
        lambda d: children(d).append(
            {
                "id": "x",
                "select": {"count": 1, "from": {"list": "nope"}},
                "source": {"url": URL, "quote": "q"},
            }
        )
    )
    assert check_references(bad, catalog()).problems == ["unknown course FSCI 99999"]
    assert check_references(listed, catalog()).problems == ["unknown course list nope"]


def test_quotes_must_be_verbatim_on_the_page() -> None:
    snap = fake_page()
    texts = {snap.id: courseleaf.page_text(snap.text())}
    assert check_quotes(rules(), texts, {URL: snap.id}).ok
    # Whitespace may differ, words may not.
    loose = edited(
        lambda d: children(d)[1].update(
            {"source": {"snapshot_id": "7", "quote": "The BS   also\nrequires FSCI 20100."}}
        )
    )
    assert check_quotes(loose, texts, {URL: snap.id}).ok
    wrong = edited(
        lambda d: children(d)[1].update(
            {"source": {"url": URL, "quote": "The BS requires FSCI 20100."}}
        )
    )
    check = check_quotes(wrong, texts, {URL: snap.id})
    assert not check.ok and "not found verbatim" in check.problems[0]
    elsewhere = edited(
        lambda d: children(d)[1].update({"source": {"url": "http://other.test/", "quote": "x"}})
    )
    assert "not fetched" in check_quotes(elsewhere, texts, {URL: snap.id}).problems[0]


def test_size_of_a_major() -> None:
    assert min_courses(rules().rules) == 3
    check = check_size(rules(), "major")
    assert not check.ok and "at least 3 courses" in check.problems[0]
    assert check_size(rules(), "minor").skipped
    big = edited(
        lambda d: children(d).append(
            {
                "id": "el",
                "select": {"count": 8, "from": {"subject": "FSCI"}},
                "source": {"url": URL, "quote": "q"},
            }
        )
    )
    assert check_size(big, "major").ok  # 11 courses
    n_of = edited(lambda d: d["rules"]["group"].update({"all": False, "n_of": 1}))
    assert min_courses(n_of.rules) == 1


def test_scored_checks() -> None:
    assert check_agreement(None).skipped
    assert not check_agreement(node_agreement(rules(), edited(lambda d: children(d).pop()))).ok
    assert check_backtranslation(None).skipped
    assert check_backtranslation([]).ok
    assert check_backtranslation([{"path": "", "problem": "missing minor rule"}]).problems == [
        "(program): missing minor rule"
    ]
    assert check_golden(None).skipped
    assert check_golden(
        GoldenOutcome("x", total=2, passed=1, failures=["p: expected pass"])
    ).problems == ["p: expected pass"]
