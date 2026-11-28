"""data/planner/plan-guideline.md and config.yaml: the planner agent's rules and limits."""

from __future__ import annotations

import pytest
from api.agents.planner.guideline import (
    PlannerConfig,
    load_guideline,
    load_planner_config,
    parse_guideline,
)
from pydantic import ValidationError

SECTIONS = [
    "How to use this file",
    "Program completion",
    "Offerings and sequences",
    "The student's standards",
    "Interests",
    "Shape of a good plan",
    "CS major facts",
    "Explaining choices",
    "Changing the plan in chat",
]


def test_guideline_rules_parse() -> None:
    g = load_guideline()
    assert len(g.rules) >= 25
    assert list(g.rules) == sorted(g.rules)
    for rule in g.rules.values():
        assert rule.id.startswith("G") and rule.id[1:].isdigit()
        assert rule.tier in {"hard", "strong", "preference", "tiebreak"}
        assert rule.text and rule.why, rule.id


def test_guideline_sections_present() -> None:
    headings = [ln[3:].strip() for ln in load_guideline().text.splitlines() if ln.startswith("## ")]
    found = [h for h in headings if any(h.startswith(s) for s in SECTIONS)]
    assert [next(s for s in SECTIONS if h.startswith(s)) for h in found] == SECTIONS


def test_guideline_cites_sources_for_facts() -> None:
    g = load_guideline()
    for section in ("Offerings and sequences", "CS major facts"):
        ids = g.sections[section]
        assert ids, section
        for rid in ids:
            src = g.rules[rid].source
            assert src and src.startswith("https://"), rid


def test_parse_guideline_rejects_duplicate_ids() -> None:
    text = "## A\n- **G01** · hard · x\n  Why: y\n- **G01** · hard · z\n  Why: w\n"
    with pytest.raises(ValueError, match="G01"):
        parse_guideline(text)


def test_parse_guideline_rejects_rule_without_why() -> None:
    with pytest.raises(ValueError, match="G02"):
        parse_guideline("## A\n- **G02** · strong · x\n")


def test_planner_config_loads() -> None:
    c = load_planner_config()
    assert (c.questions_max, c.repair_rounds, c.thrash_same_errors, c.max_ops_per_round) == (
        2,
        5,
        3,
        12,
    )
    assert (c.min_options, c.max_options, c.chat_proposals_max) == (2, 5, 3)
    assert c.fix_warning_codes == ["V04", "V10", "V11"]
    assert c.state_ttl_days == 1


def test_planner_config_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        PlannerConfig.model_validate({"repair_round": 5})
