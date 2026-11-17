"""Agents E1-E4 against FakeLLM (no API calls): tools, checks, repair turns, fallbacks."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from api.agents.prompts import load_prompt
from ingest_rules import RULES, URL, candidate, catalog, fake_page, rules, rules_yaml
from llm_gateway.api import FakeLLM, FakeTurn, LLMUnavailableError, ToolCall
from llm_gateway.routing import load_routing
from worker.ingest.e1 import formalize
from worker.ingest.e2 import (
    ReferenceList,
    enumerate_programs,
    reconcile,
    stated_counts,
)
from worker.ingest.e3 import RUN_A, RUN_B, VALIDATE_ATTEMPTS, E3Context, formalize_program
from worker.ingest.e4 import english_of, judge
from worker.ingest.golden import GoldenOutcome
from worker.ingest.llm import CostCapReachedError, Metered

PROMPTS = {
    "e1_prereq": "e1_prereq_formalizer",
    "e2_enumerator": "e2_program_enumerator",
    "e3_formalizer": "e3_program_formalizer",
    "e3b_formalizer": "e3b_second_opinion",
    "e4_backtranslation": "e4_backtranslation_judge",
}


@pytest.mark.parametrize(("name", "task"), PROMPTS.items())
def test_prompts_have_version_headers_and_routed_tasks(name: str, task: str) -> None:
    prompt = load_prompt(name)
    assert prompt.version >= 1 and prompt.task == task
    assert task in load_routing().tasks
    assert "untrusted_source" in prompt.text  # every one of them reads catalog text


def test_the_second_run_prompt_has_the_same_sections_in_another_order() -> None:
    a, b = load_prompt("e3_formalizer").text, load_prompt("e3b_formalizer").text

    def sections(text: str) -> list[str]:
        return [s.strip() for s in text.split("## ") if s.strip()]

    assert sorted(sections(a)) == sorted(sections(b))
    assert sections(a) != sections(b)


# ------------------------------------------------------------------------------- E1


def e1(answer: Any, sentence: str = "FSCI 10100 or FSCI 10150", course: str = "FSCI 10200") -> Any:
    fake = FakeLLM(script={"e1_prereq_formalizer": [answer]})
    result = formalize(fake, course=course, sentence=sentence, catalog=catalog(), snapshot_id="7")
    return fake, result


def test_e1_accepts_a_checked_expression() -> None:
    fake, result = e1({"prereq": {"any": ["FSCI 10100", "FSCI 10150"]}})
    assert result.ok and result.review is None
    assert result.expr is not None and result.expr.op == "any"
    message = fake.calls[0]["messages"][0].content
    assert '<untrusted_source id="prereq:FSCI 10200">' in message
    assert result.run is not None and result.run.kind == "e1" and result.run.status == "ok"


@pytest.mark.parametrize(
    ("answer", "sentence", "error"),
    [
        (
            {"prereq": {"any": ["FSCI 10100", "FSCI 99999"]}},
            "FSCI 10100 or FSCI 99999",
            "not in the catalog",
        ),
        ({"prereq": "FHIS 20100"}, "FSCI 10100", "does not mention"),
        ({"prereq": "FSCI 10200"}, "FSCI 10200 recommended", "its own prerequisite"),
        ({"prereq": {"all": []}}, "FSCI 10100", "does not parse"),
        (
            {"prereq": None, "unparseable": True, "note": "title only"},
            "Calculus II",
            "could not express",
        ),
        (LLMUnavailableError("down"), "FSCI 10100", "did not answer"),
    ],
)
def test_e1_failures_go_to_review(answer: Any, sentence: str, error: str) -> None:
    _, result = e1(answer, sentence)
    assert not result.ok
    assert result.review is not None and result.review.target_type == "requisite"
    assert result.review.target_id == "2099-00:FSCI 10200"
    assert any(error in e for e in result.errors), result.errors
    assert result.review.diff["raw_text"] == sentence


# ------------------------------------------------------------------------------- E2


def cand(id_: str, type_: str, family: str, url: str) -> dict[str, Any]:
    return {"id": id_, "name": id_, "type": type_, "family": family, "url": url, "evidence": []}


BASE = "http://catalog.test/thecollege"
GOOD = [
    cand("fsci-ba", "major", "Fake Science", f"{BASE}/fakescience/"),
    cand("fsci-bs", "major", "Fake Science", f"{BASE}/fakescience/"),
    cand("fsci-minor", "minor", "Fake Science", f"{BASE}/fakescience/"),
    cand("fhis-ba", "major", "Fake History", f"{BASE}/fakehistory/"),
]


def lists() -> list[ReferenceList]:
    counts = stated_counts(fake_page("programs-study", "3", "http://catalog.test/programs-study/"))
    index = ReferenceList(
        "index",
        "1",
        urls={f"{BASE}/fakescience/", f"{BASE}/fakehistory/"},
        url_types=frozenset({"major", "minor"}),
    )
    return [counts, index]


def test_stated_counts_are_read_by_code() -> None:
    counted = stated_counts(fake_page("programs-study", "3", "http://catalog.test/programs-study/"))
    assert counted.counts == {"major": 2, "minor": 1}


def test_reconciliation_needs_two_lists_and_matching_counts() -> None:
    from worker.ingest.e2 import ProgramCandidate

    good = [ProgramCandidate.model_validate(c) for c in GOOD]
    assert reconcile(good, lists()) == []
    assert "at least two are required" in reconcile(good, lists()[:1])[0]
    missing = reconcile(good[:-1], lists())
    assert any("2 majors listed, 1 proposed" in p for p in missing)
    assert any("lists http://catalog.test/thecollege/fakehistory/" in p for p in missing)
    twice = reconcile([*good, good[0]], lists())
    assert any("proposed twice" in p for p in twice)
    stray = ProgramCandidate.model_validate(cand("x-minor", "minor", "X", f"{BASE}/x/"))
    assert any("does not list" in p for p in reconcile([*good, stray], lists()))


def pages() -> list[Any]:
    return [
        fake_page("thecollege/programsofstudy", "1", f"{BASE}/programsofstudy/"),
        fake_page("thecollege/fakescience", "2", f"{BASE}/fakescience/"),
        fake_page("programs-study", "3", "http://catalog.test/programs-study/"),
    ]


def test_e2_agent_reads_pages_and_its_count_reconciles() -> None:
    fake = FakeLLM(
        script={
            "e2_program_enumerator": [
                ToolCall("list_pages", {}),
                ToolCall("read_snapshot", {"id": "2", "start": 0, "end": 500}),
                # Evidence naming a page that does not exist gets one repair turn.
                ToolCall("submit_programs", {"candidates": [{**GOOD[0], "evidence": ["99"]}]}),
                ToolCall(
                    "submit_programs", {"candidates": [{**c, "evidence": ["2"]} for c in GOOD]}
                ),
            ]
        }
    )
    out = enumerate_programs(fake, catalog_year="2099-00", pages=pages(), lists=lists())
    assert not out.blocked, out.problems
    assert [c.id for c in out.candidates] == ["fsci-ba", "fsci-bs", "fsci-minor", "fhis-ba"]
    assert fake.calls[0]["tools"] == ["list_pages", "read_snapshot", "submit_programs"]
    read = fake.calls[2]["messages"][-1]["content"][0]["content"]
    assert '<untrusted_source id="snapshot:2">' in read
    assert out.run is not None and out.run.status == "ok"


def test_e2_mismatch_blocks_the_run() -> None:
    fake = FakeLLM(
        script={"e2_program_enumerator": [ToolCall("submit_programs", {"candidates": GOOD[:2]})]}
    )
    out = enumerate_programs(fake, catalog_year="2099-00", pages=pages(), lists=lists())
    assert out.blocked
    review = out.review("2099-00")
    assert review.target_type == "ingest_run" and "stopped" in review.reason


def test_e2_unavailable_blocks_too() -> None:
    out = enumerate_programs(FakeLLM(), catalog_year="2099-00", pages=pages(), lists=lists())
    assert out.blocked and "did not finish" in out.problems[0]


# ------------------------------------------------------------------------------- E3


def ctx(golden: Any = None) -> E3Context:
    return E3Context(candidate(), "2099-00", [fake_page()], catalog(), golden)


def submit(text: str) -> ToolCall:
    return ToolCall("submit_rules", {"rules_yaml": text, "notes": "n"})


def test_e3_uses_its_tools_and_submits_a_valid_tree() -> None:
    golden_calls: list[str] = []

    def golden(r: Any) -> GoldenOutcome:
        golden_calls.append(r.id)
        return GoldenOutcome(r.id, total=1, passed=1)

    bad = copy.deepcopy(RULES)
    bad["rules"]["group"]["children"][1]["slot"]["any_of"] = ["FSCI 99999"]
    fake = FakeLLM(
        script={
            "e3_program_formalizer": [
                ToolCall("read_snapshot", {"id": "7", "start": 0, "end": 4000}),
                [
                    ToolCall("lookup_course", {"code": "fsci 10100"}),
                    ToolCall("get_course_list", {"name": "fake-list"}),
                ],
                ToolCall("run_golden", {"program": "fsci-bs"}),  # nothing validated yet
                ToolCall("validate_rules", {"rules_yaml": rules_yaml(bad)}),
                ToolCall("validate_rules", {"rules_yaml": rules_yaml()}),
                ToolCall("run_golden", {"program": "fsci-bs"}),
                submit(rules_yaml()),
            ]
        }
    )
    run = formalize_program(fake, ctx(golden), RUN_A)
    assert run.rules is not None and run.error is None
    assert run.rules == rules()
    assert run.validate_attempts == 2
    assert golden_calls == ["fsci-bs", "fsci-bs"]  # the tool, then the final check
    assert fake.calls[0]["tools"] == [
        "read_snapshot", "lookup_course", "get_course_list", "validate_rules", "run_golden", "submit_rules",
    ]  # fmt: skip
    results = [m for m in fake.calls[-1]["messages"] if m["role"] == "user"]
    texts = [b["content"] for m in results[1:] for b in m["content"]]
    assert '<untrusted_source id="snapshot:7">' in texts[0]
    assert '"title":"Fake FSCI 10100"' in texts[1]
    assert "validate_rules first" in texts[3]
    assert '"ok":false' in texts[4] and "unknown course FSCI 99999" in texts[4]
    assert '"ok":true' in texts[5] and "at least 3 courses" in texts[5]  # (g) is a warning
    assert texts[6] == "1/1 golden plans behave as expected"
    assert run.warnings and run.warnings[0].id == "g"
    assert run.run is not None and run.run.kind == "e3" and run.run.input_snapshot_ids == ["7"]


def test_e3_validation_attempts_are_capped() -> None:
    calls = [
        ToolCall("validate_rules", {"rules_yaml": "id: [broken"})
        for _ in range(VALIDATE_ATTEMPTS + 1)
    ]
    fake = FakeLLM(script={"e3_program_formalizer": [*calls, submit(rules_yaml())]})
    run = formalize_program(fake, ctx(), RUN_A)
    assert run.rules is not None
    assert run.validate_attempts == VALIDATE_ATTEMPTS
    last = fake.calls[-1]["messages"][-1]["content"][0]
    assert "No validation attempts left" in last["content"]


def test_e3_a_bad_quote_gets_one_repair_turn_then_fails() -> None:
    bad = copy.deepcopy(RULES)
    bad["rules"]["source"] = {"url": URL, "quote": "Words that are not on the page."}
    fake = FakeLLM(
        script={"e3_program_formalizer": [submit(rules_yaml(bad)), submit(rules_yaml(bad))]}
    )
    run = formalize_program(fake, ctx(), RUN_A)
    assert run.rules is None and run.error is not None and "invalid_output" in run.error
    assert "not found verbatim" in run.error
    assert run.run is not None and run.run.status == "failed"


def test_e3_refuses_a_tree_for_another_program() -> None:
    other = {**RULES, "id": "other"}
    fake = FakeLLM(
        script={"e3_program_formalizer": [submit(rules_yaml(other)), submit(rules_yaml())]}
    )
    run = formalize_program(fake, ctx(), RUN_A)
    assert run.rules is not None  # repaired on the second try


def test_e3b_is_a_different_task_prompt_and_message_order() -> None:
    fake = FakeLLM(script={"e3b_second_opinion": [submit(rules_yaml())]})
    run = formalize_program(fake, ctx(), RUN_B)
    assert run.rules is not None and run.run is not None and run.run.kind == "e3b"
    call = fake.calls[0]
    assert call["task"] == "e3b_second_opinion"
    assert call["system"].startswith("## Worked examples")
    assert call["messages"][0]["content"].startswith("Fetched pages")


def test_e3_with_no_model_fails_cleanly() -> None:
    run = formalize_program(FakeLLM(), ctx(), RUN_A)
    assert run.rules is None and run.run is not None and run.run.status == "failed"


# ------------------------------------------------------------------------------- E4


def test_e4_keeps_differences_on_known_paths() -> None:
    fake = FakeLLM(
        script={
            "e4_backtranslation_judge": [
                {
                    "english": "Take FSCI 10100 ...",
                    "differences": [
                        {
                            "path": "fsci-bs/methods",
                            "problem": "the page says a quality grade is required",
                        },
                        {"path": "fsci-bs/nope", "problem": "invented path"},
                    ],
                }
            ]
        }
    )
    result = judge(fake, rules(), [("7", "page text")])
    assert result.differences == [
        {"path": "fsci-bs/methods", "problem": "the page says a quality grade is required"},
        {"path": "", "problem": "(about fsci-bs/nope) invented path"},
    ]
    assert result.dropped == 1 and result.run.status == "review"
    assert '<untrusted_source id="snapshot:7">' in fake.calls[0]["messages"][0].content


def test_e4_unavailable_is_skipped_not_passed() -> None:
    result = judge(FakeLLM(), rules(), [("7", "x")])
    assert result.differences is None and result.run.status == "failed"


def test_english_rendering() -> None:
    text = english_of(rules())
    assert "- Fake Science BS: All of the following" in text
    assert "One of: FSCI 10100, FSCI 10150" in text
    assert "FSCI 20100 (no pass/fail)" in text


# ---------------------------------------------------------------------------- meter


def test_the_spending_cap_stops_calls() -> None:
    fake = FakeLLM(script={"e1_prereq_formalizer": [{"prereq": "FSCI 10100"}]})
    metered = Metered(fake, cap_usd=0.0)
    with pytest.raises(CostCapReachedError):
        metered.structured(
            "e1_prereq_formalizer", system="", messages=[], schema=dict, prompt_version="x"
        )
    turn = FakeTurn(calls=(submit(rules_yaml()),))
    agent = Metered(FakeLLM(script={"e3_program_formalizer": [turn]}), cap_usd=100.0)
    run = formalize_program(agent, ctx(), RUN_A)
    assert (
        run.rules is not None
        and agent.calls == 1
        and agent.model_for("e3_program_formalizer") == "fake"
    )
