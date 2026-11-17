"""The LiveBudgetGuard, the ledger and the recordings (prompt 13), tested with fake backends
only: no network, no API key."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from llm_gateway.live import (
    PHASE_CAPS_USD,
    TOTAL_CAP_USD,
    BudgetExceeded,
    GuardedGateway,
    Ledger,
    LedgerEntry,
    LiveBudgetGuard,
    Recorder,
    replay_gateway,
    secrets_in,
    worst_case_usd,
)
from llm_gateway.loop import Backend
from llm_gateway.routing import Routing
from llm_gateway.types import (
    AgentError,
    LLMUnavailableError,
    Message,
    ModelRequest,
    ModelTurn,
    ProviderError,
    ToolCall,
    Usage,
)
from pydantic import BaseModel

ROUTING = Routing.model_validate(
    {
        "version": 1,
        "providers": {"primary": "anthropic", "fallback": "openrouter", "fallback_after_errors": 2},
        "tasks": {
            "cheap": {
                "model": "claude-haiku-5-5",
                "max_tokens": 200,
                "fallback": {"provider": "openrouter", "model": "anthropic/claude-haiku-5.5"},
            },
            "pricey": {"model": "claude-opus-5-5", "max_tokens": 16000},
            "unpriced": {"model": "claude-mystery", "max_tokens": 100},
        },
        "prices": {
            "claude-haiku-5-5": {
                "input": 0.10,
                "output": 0.50,
                "cache_read": 0.01,
                "cache_write": 0.125,
            },
            "anthropic/claude-haiku-5.5": {
                "input": 0.10,
                "output": 0.50,
                "cache_read": 0.01,
                "cache_write": 0.125,
            },
            "claude-opus-5-5": {
                "input": 4.00,
                "output": 20.00,
                "cache_read": 0.20,
                "cache_write": 5.00,
            },
        },
    }
)


class Answer(BaseModel):
    label: str


class FakeProvider(Backend):
    """Answers every call with a `submit` tool call; counts calls. Has an `api_key` attribute
    so the tests can prove it never reaches the ledger or a recording."""

    def __init__(self, name: str = "anthropic", usage: Usage | None = None) -> None:
        self.name = name
        self.api_key = "sk-test-NEVER-WRITTEN"
        self.calls = 0
        self.usage = usage or Usage(input_tokens=1000, output_tokens=100)

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.calls += 1
        call = ToolCall("submit", {"label": "ok"}, f"toolu_{self.calls}")
        return ModelTurn(
            content=[{"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}],
            tool_calls=[call],
            text="",
            usage=self.usage,
            stop_reason="tool_use",
            model=request.model,
        )


def guard(tmp_path: Path, caps: dict[str, float] | None = None) -> LiveBudgetGuard:
    return LiveBudgetGuard(
        Ledger(tmp_path / "ledger.jsonl"),
        ROUTING,
        phase_caps=caps or {"phase0": 0.50, "phase1": 1.00},
    )


def ask(gateway: GuardedGateway, task: str = "cheap") -> Answer:
    return gateway.structured(
        task,
        system="Label it.",
        messages=[Message("user", "hello")],
        schema=Answer,
        prompt_version="t1",
    )


def entry(phase: str, cost: float) -> LedgerEntry:
    return LedgerEntry(
        time="2026-11-16T08:00:00+00:00",
        test_id="t",
        phase=phase,
        task="cheap",
        provider="anthropic",
        model="claude-haiku-5-5",
        input_tokens=1,
        output_tokens=1,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=cost,
        latency_ms=1,
        ok=True,
    )


def test_the_caps_are_prompt_13s() -> None:
    assert TOTAL_CAP_USD == 4.50
    assert PHASE_CAPS_USD == {
        "phase0": 0.10,
        "phase1": 1.80,
        "phase2": 0.40,
        "phase3": 1.40,
        "phase4": 0.30,
        "phase5": 0.50,
    }


def test_the_ledger_appends_and_sums(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "live" / "ledger.jsonl")
    assert ledger.total() == 0.0 and ledger.entries() == []
    ledger.append(entry("phase0", 0.25))
    ledger.append(entry("phase1", 0.5))
    assert ledger.total() == 0.75 and ledger.phase_total("phase0") == 0.25
    assert len(Ledger(tmp_path / "live" / "ledger.jsonl").entries()) == 2  # read back from disk


def test_a_call_is_charged_recorded_and_attributed(tmp_path: Path) -> None:
    g = guard(tmp_path)
    provider = FakeProvider()
    gateway = GuardedGateway(
        ROUTING, primary=provider, fallback=None, guard=g, recorder=Recorder(tmp_path / "rec")
    )
    with g.running("phase0", "smoke-haiku"):
        assert ask(gateway).label == "ok"
    [row] = g.ledger.entries()
    assert (row.phase, row.test_id, row.task, row.model, row.ok) == (
        "phase0",
        "smoke-haiku",
        "cheap",
        "claude-haiku-5-5",
        True,
    )
    assert row.cost_usd == pytest.approx((1000 * 0.10 + 100 * 0.50) / 1_000_000)
    recorded = (tmp_path / "rec" / "smoke-haiku.json").read_text()
    assert json.loads(recorded)[0]["response"]["tool_calls"][0]["name"] == "submit"
    everything = recorded + (tmp_path / "ledger.jsonl").read_text()
    assert provider.api_key not in everything and "api_key" not in everything


def test_the_worst_case_counts_every_output_token(tmp_path: Path) -> None:
    request = ModelRequest(
        model="claude-opus-5-5",
        system="x" * 3000,
        messages=[],
        tools=[],
        max_tokens=16000,
        effort=None,
        timeout_s=30,
    )
    worst = worst_case_usd(ROUTING, "claude-opus-5-5", request)
    assert worst >= 16000 * 20.00 / 1_000_000  # $0.32 of output alone
    assert worst_case_usd(ROUTING, "claude-mystery", request) == math.inf


def test_a_call_that_could_pass_the_total_cap_is_refused_before_it_is_sent(tmp_path: Path) -> None:
    g = guard(tmp_path, {"phase1": 10.0})
    g.ledger.append(entry("phase1", 4.40))  # earlier runs spent $4.40
    provider = FakeProvider()
    gateway = GuardedGateway(ROUTING, primary=provider, fallback=None, guard=g, recorder=None)
    with g.running("phase1", "a1-profile-1"), pytest.raises(BudgetExceeded, match="total cap"):
        ask(gateway, "pricey")  # worst case > $0.10
    assert provider.calls == 0 and g.refused
    # Once refused, nothing more goes out, even a call that would fit.
    with g.running("phase1", "a2-case-1"), pytest.raises(BudgetExceeded, match="stopped earlier"):
        ask(gateway, "cheap")
    assert provider.calls == 0 and g.ledger.total() == pytest.approx(4.40)


def test_a_phase_cap_is_enforced_and_a_call_needs_a_phase(tmp_path: Path) -> None:
    g = guard(tmp_path, {"phase0": 0.05, "phase1": 1.00})
    g.ledger.append(entry("phase0", 0.0499))  # worst case of a Haiku call is ~$0.0002
    gateway = GuardedGateway(ROUTING, primary=FakeProvider(), fallback=None, guard=g, recorder=None)
    with g.running("phase0", "smoke"), pytest.raises(BudgetExceeded, match="phase0 passes its"):
        ask(gateway)
    fresh = guard(tmp_path / "other")
    gateway = GuardedGateway(
        ROUTING, primary=FakeProvider(), fallback=None, guard=fresh, recorder=None
    )
    with pytest.raises(BudgetExceeded, match="no budget phase"):
        ask(gateway)  # outside any `running` block


def test_an_unpriced_model_is_never_called(tmp_path: Path) -> None:
    g = guard(tmp_path)
    provider = FakeProvider()
    gateway = GuardedGateway(ROUTING, primary=provider, fallback=None, guard=g, recorder=None)
    with g.running("phase0", "x"), pytest.raises(BudgetExceeded):
        ask(gateway, "unpriced")
    assert provider.calls == 0


def test_a_refusal_does_not_fall_through_to_the_fallback_provider(tmp_path: Path) -> None:
    g = guard(tmp_path, {"phase0": 0.0})
    primary, fallback = FakeProvider("anthropic"), FakeProvider("openrouter")
    gateway = GuardedGateway(ROUTING, primary=primary, fallback=fallback, guard=g, recorder=None)
    with g.running("phase0", "x"), pytest.raises(BudgetExceeded):
        ask(gateway)
    assert primary.calls == fallback.calls == 0
    assert isinstance(
        BudgetExceeded("x"), LLMUnavailableError
    )  # app agents take their fallback path


def test_a_failed_provider_call_costs_nothing_but_is_logged(tmp_path: Path) -> None:
    class Down(FakeProvider):
        def complete(self, request: ModelRequest) -> ModelTurn:
            self.calls += 1
            raise ProviderError("500", fatal=True)

    g = guard(tmp_path)
    gateway = GuardedGateway(ROUTING, primary=Down(), fallback=None, guard=g, recorder=None)
    with g.running("phase0", "down"), pytest.raises(AgentError):
        ask(gateway)
    [row] = g.ledger.entries()
    assert not row.ok and row.cost_usd == 0.0


def test_a_recording_replays_without_a_provider(tmp_path: Path) -> None:
    g = guard(tmp_path)
    gateway = GuardedGateway(
        ROUTING, primary=FakeProvider(), fallback=None, guard=g, recorder=Recorder(tmp_path / "rec")
    )
    with g.running("phase0", "case-1"):
        live = ask(gateway)
    replay = replay_gateway(ROUTING, tmp_path / "rec" / "case-1.json")
    assert (
        replay.structured(
            "cheap",
            system="Label it.",
            messages=[Message("user", "hello")],
            schema=Answer,
            prompt_version="t1",
        )
        == live
    )
    with pytest.raises(AgentError):  # the recording has one turn only
        replay.structured(
            "cheap",
            system="s",
            messages=[Message("user", "again")],
            schema=Answer,
            prompt_version="t1",
        )
    assert g.ledger.total() == pytest.approx(
        (1000 * 0.10 + 100 * 0.50) / 1_000_000
    )  # replay spent nothing


def test_the_ledger_survives_a_restart(tmp_path: Path) -> None:
    """A new run (a new guard over the same ledger file) starts from what was spent."""
    first = guard(tmp_path, {"phase1": 10.0})
    gateway = GuardedGateway(
        ROUTING, primary=FakeProvider(), fallback=None, guard=first, recorder=None
    )
    with first.running("phase1", "a"):
        ask(gateway)
    spent = first.spent()
    assert spent > 0
    second = LiveBudgetGuard(
        Ledger(tmp_path / "ledger.jsonl"),
        ROUTING,
        phase_caps={"phase1": 10.0},
        total_cap_usd=spent + 0.0001,
    )
    gateway = GuardedGateway(
        ROUTING, primary=FakeProvider(), fallback=None, guard=second, recorder=None
    )
    with second.running("phase1", "b"), pytest.raises(BudgetExceeded, match="total cap"):
        ask(gateway)


def test_cache_tokens_are_charged_at_their_own_prices(tmp_path: Path) -> None:
    g = guard(tmp_path, {"phase0": 1.0})
    usage = Usage(
        input_tokens=100, output_tokens=50, cache_read_tokens=4000, cache_write_tokens=2000
    )
    gateway = GuardedGateway(
        ROUTING, primary=FakeProvider(usage=usage), fallback=None, guard=g, recorder=None
    )
    with g.running("phase0", "cache"):
        ask(gateway)
    [row] = g.ledger.entries()
    assert (row.cache_read_tokens, row.cache_write_tokens) == (4000, 2000)
    expected = (100 * 0.10 + 50 * 0.50 + 4000 * 0.01 + 2000 * 0.125) / 1_000_000
    assert row.cost_usd == pytest.approx(expected)


def test_recordings_hold_no_key_or_auth_header(tmp_path: Path) -> None:
    clean = tmp_path / "clean.json"
    clean.write_text('[{"request": {"system": "hi"}}]')
    leaked = tmp_path / "leaked.json"
    leaked.write_text('{"headers": {"x-api-key": "abc"}, "k": "sk-ant-api03-ABCDEFGHIJKL"}')
    configured = tmp_path / "configured.json"
    configured.write_text('{"note": "the-real-key-value-123"}')
    assert secrets_in([clean], known=["the-real-key-value-123"]) == []
    found = secrets_in([leaked, configured], known=["the-real-key-value-123"])
    assert any(f.startswith("leaked.json") for f in found)
    assert "configured.json: contains a configured API key" in found
    assert not any("the-real-key-value-123" in f for f in found)
