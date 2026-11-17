"""The shared agent loop: budgets, validation with one repair turn, provider fallback, cost
logging. Every test runs on fakes; nothing talks to a provider."""

from __future__ import annotations

from typing import Any

import pytest
from llm_gateway.api import (
    AgentError,
    AgentSpec,
    Budget,
    FakeLLM,
    FakeTurn,
    Message,
    SubmitTool,
    Tool,
    ToolCall,
    ToolOutput,
    UnavailableLLM,
    run_agent,
)
from llm_gateway.gateway import Gateway, build_gateway
from llm_gateway.loop import Backend, Leg, run_loop
from llm_gateway.routing import Routing, TaskRoute, load_routing
from llm_gateway.types import ModelRequest, ModelTurn, ProviderError, Usage
from pydantic import BaseModel, Field


class Answer(BaseModel):
    text: str = Field(max_length=40)
    cites: list[str] = []


def _no_x(a: Answer) -> None:
    if "x" in a.text:
        raise ValueError("text must not contain x")


def lookup(args: dict[str, Any]) -> ToolOutput:
    code = args["code"]
    return ToolOutput(f'{{"code": "{code}"}}', ids=frozenset({f"course:{code}"}))


DEFAULT_BUDGET = Budget()


def spec(budget: Budget = DEFAULT_BUDGET, **kw: Any) -> AgentSpec[Answer]:
    return AgentSpec(
        task="t",
        prompt_version="t@1",
        system="sys",
        messages=[Message("user", "hello")],
        tools=[
            Tool(
                "lookup",
                "Look a course up.",
                {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                    "additionalProperties": False,
                },
                lookup,
            )
        ],
        submit=SubmitTool("submit_answer", "Answer.", Answer, check=_no_x),
        budget=budget,
        **kw,
    )


def test_tool_calls_then_submit_collects_cited_ids() -> None:
    fake = FakeLLM(
        script={
            "t": [
                [ToolCall("lookup", {"code": "MATH 20700"}), ToolCall("lookup", {"code": "A 1"})],
                ToolCall("submit_answer", {"text": "ok", "cites": ["course:MATH 20700"]}),
            ]
        }
    )
    result = fake.run_agent(spec(known_ids=["plan"]))
    assert result.output.text == "ok"
    assert result.seen_ids == {"course:MATH 20700", "course:A 1", "plan"}
    assert [c.name for c in result.tool_calls] == ["lookup", "lookup", "submit_answer"]
    # The second request carries both tool results, in one user message.
    second = fake.calls[1]["messages"]
    assert second[-1]["role"] == "user" and len(second[-1]["content"]) == 2
    assert {b["type"] for b in second[-1]["content"]} == {"tool_result"}
    assert len(fake.records) == 2 and all(r.ok for r in fake.records)
    assert result.tokens == 240


def test_tool_call_budget_exhaustion_fails_the_run() -> None:
    fake = FakeLLM(script={"t": [ToolCall("lookup", {"code": f"A {i}"}) for i in range(5)]})
    with pytest.raises(AgentError) as err:
        fake.run_agent(spec(Budget(tool_calls=3)))
    assert err.value.reason == "budget_tool_calls"


def test_token_budget_exhaustion_fails_the_run() -> None:
    big = FakeTurn(calls=(ToolCall("lookup", {"code": "A 1"}),), usage=Usage(5000, 100))
    fake = FakeLLM(script={"t": [big, big]})
    with pytest.raises(AgentError) as err:
        fake.run_agent(spec(Budget(tokens=8000)))
    assert err.value.reason == "budget_tokens"


def test_time_budget_exhaustion_fails_the_run() -> None:
    now = [0.0]

    def clock() -> float:
        now[0] += 10.0
        return now[0]

    class Slow(Backend):
        def complete(self, request: ModelRequest) -> ModelTurn:
            return ModelTurn(
                [{"type": "tool_use", "id": "1", "name": "lookup", "input": {"code": "A 1"}}],
                [ToolCall("lookup", {"code": "A 1"}, "1")],
                "",
                Usage(1, 1),
                "tool_use",
                "m",
            )

    with pytest.raises(AgentError) as err:
        run_loop(
            spec(Budget(seconds=35)),
            route=TaskRoute(model="m", max_tokens=10),
            routing=Routing(version=1, tasks={}),
            legs=[Leg(Slow(), "m")],
            clock=clock,
        )
    assert err.value.reason == "budget_seconds"


def test_invalid_output_gets_one_repair_turn() -> None:
    fake = FakeLLM(
        script={
            "t": [
                ToolCall("submit_answer", {"text": "x" * 50}),
                ToolCall("submit_answer", {"text": "fine"}),
            ]
        }
    )
    assert fake.run_agent(spec()).output.text == "fine"
    repair = fake.calls[1]["messages"][-1]["content"][0]
    assert repair["is_error"] and "invalid" in repair["content"]


def test_invalid_output_twice_fails() -> None:
    fake = FakeLLM(
        script={
            "t": [
                ToolCall("submit_answer", {"text": "x" * 50}),
                ToolCall("submit_answer", {"text": "has x"}),  # passes the schema, fails check
                ToolCall("submit_answer", {"text": "fine"}),
            ]
        }
    )
    with pytest.raises(AgentError) as err:
        fake.run_agent(spec())
    assert err.value.reason == "invalid_output"
    assert "must not contain x" in str(err.value)


def test_plain_text_answer_counts_as_the_repair() -> None:
    fake = FakeLLM(script={"t": ["Here is my answer", "Still text"]})
    with pytest.raises(AgentError) as err:
        fake.run_agent(spec())
    assert err.value.reason == "invalid_output"
    assert "submit_answer" in fake.calls[1]["messages"][-1]["content"]


def test_unknown_tool_and_tool_errors_go_back_to_the_model() -> None:
    def broken(_: dict[str, Any]) -> ToolOutput:
        raise RuntimeError("database down")

    s = spec()
    s.tools.append(Tool("broken", "b", {"type": "object"}, broken))
    fake = FakeLLM(
        script={
            "t": [
                [ToolCall("apply_change_set", {}), ToolCall("broken", {})],
                ToolCall("submit_answer", {"text": "ok"}),
            ]
        }
    )
    assert fake.run_agent(s).output.text == "ok"
    results = fake.calls[1]["messages"][-1]["content"]
    assert all(r["is_error"] for r in results)
    assert "Unknown tool" in results[0]["content"]


def test_refusal_ends_the_run() -> None:
    fake = FakeLLM(script={"t": [FakeTurn(text="no", stop_reason="refusal")]})
    with pytest.raises(AgentError) as err:
        fake.run_agent(spec())
    assert err.value.reason == "refusal"
    assert fake.records[0].ok is False


class Flaky(Backend):
    def __init__(self, name: str, errors: int, fatal: bool = False) -> None:
        self.name = name
        self.errors = errors
        self.fatal = fatal
        self.seen: list[str] = []

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.seen.append(request.model)
        if self.errors:
            self.errors -= 1
            raise ProviderError("boom", fatal=self.fatal)
        call = ToolCall("submit_answer", {"text": f"from {self.name}"}, "c1")
        return ModelTurn(
            [{"type": "tool_use", "id": "c1", "name": call.name, "input": call.input}],
            [call],
            "",
            Usage(1000, 100, cache_read_tokens=2000),
            "tool_use",
            request.model,
        )


def _gateway(primary: Backend, fallback: Backend, sink: Any) -> Gateway:
    routing = Routing.model_validate(
        {
            "version": 1,
            "tasks": {
                "t": {
                    "model": "primary-model",
                    "max_tokens": 100,
                    "fallback": {"provider": "openrouter", "model": "fallback-model"},
                }
            },
            "prices": {
                "primary-model": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 5},
                "fallback-model": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 5},
            },
        }
    )
    return Gateway(routing, primary=primary, fallback=fallback, sink=sink)


def test_one_provider_error_is_retried_on_the_same_provider() -> None:
    primary, fallback = Flaky("anthropic", 1), Flaky("openrouter", 0)
    records: list[Any] = []
    result = _gateway(primary, fallback, records.append).run_agent(spec())
    assert result.output.text == "from anthropic" and fallback.seen == []
    assert [r.ok for r in records] == [False, True]
    # 1000 in x $4 + 100 out x $20 + 2000 cache reads x $0.20, per million tokens
    assert records[1].cost_usd == pytest.approx(0.0064)
    assert records[1].in_tokens == 3000 and records[1].model == "primary-model"


def test_fallback_after_two_provider_errors() -> None:
    primary, fallback = Flaky("anthropic", 2), Flaky("openrouter", 0)
    result = _gateway(primary, fallback, lambda r: None).run_agent(spec())
    assert result.output.text == "from openrouter"
    assert fallback.seen == ["fallback-model"]


def test_a_fatal_error_switches_provider_at_once() -> None:
    primary, fallback = Flaky("anthropic", 1, fatal=True), Flaky("openrouter", 0)
    result = _gateway(primary, fallback, lambda r: None).run_agent(spec())
    assert result.output.text == "from openrouter" and primary.seen == ["primary-model"]


def test_both_providers_failing_is_a_provider_failure() -> None:
    primary, fallback = Flaky("anthropic", 9), Flaky("openrouter", 9)
    with pytest.raises(AgentError) as err:
        _gateway(primary, fallback, lambda r: None).run_agent(spec())
    assert err.value.reason == "provider"
    assert len(primary.seen) == 2 and len(fallback.seen) == 2


def test_structured_is_a_run_with_only_a_submit_tool() -> None:
    class Label(BaseModel):
        label: str

    class Labeller(Backend):
        def complete(self, request: ModelRequest) -> ModelTurn:
            assert [t.name for t in request.tools] == ["submit"]
            call = ToolCall("submit", {"label": "ok"}, "1")
            return ModelTurn([], [call], "", Usage(1, 1), "tool_use", request.model)

    gw = _gateway(Labeller(), Labeller(), lambda r: None)
    out = gw.structured(
        "t", system="s", messages=[Message("user", "x")], schema=Label, prompt_version="v1"
    )
    assert out.label == "ok"


def test_unavailable_client_and_build_without_keys() -> None:
    with pytest.raises(AgentError) as err:
        run_agent(UnavailableLLM(), spec())
    assert err.value.reason == "unavailable"
    with pytest.raises(AgentError):
        run_agent(object(), spec())
    assert build_gateway(anthropic_api_key="", openrouter_api_key="") is None


def test_the_repository_routing_file_has_prices_for_every_model() -> None:
    routing = load_routing()
    for name, route in routing.tasks.items():
        assert route.model in routing.prices, name
        assert route.fallback is not None and route.fallback.model in routing.prices, name


def test_a_response_cut_off_at_max_tokens_runs_no_tools() -> None:
    """Live, the advisor's replies stopped at max_tokens part-way through a tool call: the tool
    arrived with input {}, failed, and the model tried again nine times (2026-11-16). A cut-off
    turn now ends the run at once: no tool runs, no further model calls."""
    ran: list[dict[str, Any]] = []

    def count(args: dict[str, Any]) -> ToolOutput:
        ran.append(args)
        return ToolOutput("{}")

    s = spec()
    s.tools.append(Tool("propose", "p", {"type": "object"}, count))
    fake = FakeLLM(
        script={"t": [FakeTurn(calls=(ToolCall("propose", {}),), stop_reason="max_tokens")]}
    )
    with pytest.raises(AgentError) as err:
        fake.run_agent(s)
    assert err.value.reason == "truncated"
    assert ran == [] and len(fake.calls) == 1
