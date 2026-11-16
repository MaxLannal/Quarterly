"""Bugs found by the live agent tests (prompt 13), replayed from their recordings: no API call.
Each recording is the real request/answer pair saved by evals/live (`evals/live/recordings`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from api.seed.bundle import build_requisites, load_bundle
from llm_gateway.live import replay_gateway
from llm_gateway.routing import load_routing
from planner_core.dsl import expr_to_text
from worker.ingest.catalog import from_bundle
from worker.ingest.e1 import formalize

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures" / "live"


@pytest.mark.parametrize("course", ["CMSC 14100", "CAAM 37710"])
def test_e1_reads_an_expression_the_model_sent_as_a_json_string(course: str) -> None:
    """Live finding (phase 4): Haiku 5.5 answered `prereq` as a JSON-encoded string
    ('{"any": [...]}'), which was read as one course code, so 20 of 20 sentences failed."""
    bundle = load_bundle(ROOT / "data" / "seed" / "2026-27")
    seed = next(c for c in bundle.courses if c.code == course)
    hand = {r.course: r.prereq for r in build_requisites(bundle) if r.prereq is not None}[course]
    gateway = replay_gateway(load_routing(), FIXTURES / f"p4-e1-{course.replace(' ', '')}.json")
    result = formalize(gateway, course=course, sentence=seed.prereq_text or "", catalog=from_bundle(bundle))
    assert result.expr is not None, result.errors
    assert not [e for e in result.errors if e.startswith("does not parse")]
    if course == "CMSC 14100":
        assert result.ok and expr_to_text(result.expr) == expr_to_text(hand)
