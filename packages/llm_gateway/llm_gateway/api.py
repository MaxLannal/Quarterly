"""The contract between the LLM gateway and its callers (set before prompts 07 and 08 ran in
parallel; prompt 07 built the real client behind it, `llm_gateway.gateway.Gateway`).

Callers ask for a *structured* answer: a Pydantic model validated from the model's output.
Agent harnesses use `run_agent` (a tool loop with a budget and a `submit_*` tool; see
`llm_gateway.loop`). `get_llm()` returns the configured client; tests use `FakeLLM`. Until an
application configures a real client, `get_llm()` returns `UnavailableLLM`, which refuses
every call, so every caller takes its fallback path.

Model ids never appear in code: a call names its *task* (a key of `llm_routing.yaml`).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from llm_gateway.loop import Backend, Leg, run_loop
from llm_gateway.routing import Routing, TaskRoute
from llm_gateway.types import (
    AgentError,
    AgentResult,
    AgentSpec,
    Budget,
    CallRecord,
    CallSink,
    LLMUnavailableError,
    Message,
    ModelRequest,
    ModelTurn,
    ProviderError,
    SubmitTool,
    Tool,
    ToolCall,
    ToolOutput,
    Usage,
)

__all__ = [
    "LLM",
    "AgentError",
    "AgentLLM",
    "AgentResult",
    "AgentSpec",
    "Budget",
    "CallRecord",
    "FakeLLM",
    "FakeTurn",
    "LLMUnavailableError",
    "Message",
    "SubmitTool",
    "Tool",
    "ToolCall",
    "ToolOutput",
    "UnavailableLLM",
    "get_llm",
    "set_llm",
]

T = TypeVar("T", bound=BaseModel)


class LLM(Protocol):
    def structured(
        self,
        task: str,
        *,
        system: str,
        messages: list[Message],
        schema: type[T],
        prompt_version: str,
        timeout_s: float | None = None,
    ) -> T:
        """Return `schema` validated from the model's answer (one repair turn allowed), or
        raise `LLMUnavailableError`."""
        ...


@runtime_checkable
class AgentLLM(Protocol):
    def run_agent(self, spec: AgentSpec[T], *, sink: CallSink | None = None) -> AgentResult[T]:
        """Run a tool loop to a validated `submit_*` payload, or raise `AgentError` (a
        `LLMUnavailableError`)."""
        ...


def run_agent[R: BaseModel](
    llm: object, spec: AgentSpec[R], *, sink: CallSink | None = None
) -> AgentResult[R]:
    """`llm.run_agent(spec)` for any configured client; a client without a tool loop is
    treated as unavailable."""
    if not isinstance(llm, AgentLLM):
        raise AgentError("unavailable", "the configured client has no tool loop")
    return llm.run_agent(spec, sink=sink)


class UnavailableLLM:
    """The default until a real client is configured: refuses every call."""

    def structured(self, task: str, **_: Any) -> Any:
        raise LLMUnavailableError(f"no LLM client is configured (task {task})")

    def run_agent(self, spec: AgentSpec[T], *, sink: CallSink | None = None) -> AgentResult[T]:
        raise AgentError("unavailable", f"no LLM client is configured (task {spec.task})")


# ------------------------------------------------------------------------------- fakes


@dataclass(frozen=True)
class FakeTurn:
    """One scripted model turn: tool calls (possibly none) and text."""

    calls: tuple[ToolCall, ...] = ()
    text: str = ""
    usage: Usage = field(default_factory=lambda: Usage(input_tokens=100, output_tokens=20))
    stop_reason: str = ""


class _ScriptedBackend(Backend):
    name = "fake"

    def __init__(self, fake: FakeLLM, task: str) -> None:
        self.fake = fake
        self.task = task
        self._ids = itertools.count(1)

    def complete(self, request: ModelRequest) -> ModelTurn:
        call = {
            "task": self.task,
            "system": request.system,
            "messages": request.messages,
            "tools": [t.name for t in request.tools],
        }
        self.fake.calls.append(call)
        if self.fake.on_call is not None:
            self.fake.on_call(call)
        answers = self.fake.script.get(self.task, [])
        if not answers:
            raise ProviderError(f"FakeLLM has no scripted turn for {self.task}", fatal=True)
        turn = _as_turn(answers.pop(0))
        calls = [
            ToolCall(c.name, c.input, c.id or f"toolu_fake_{next(self._ids)}") for c in turn.calls
        ]
        content: list[dict[str, Any]] = []
        if turn.text:
            content.append({"type": "text", "text": turn.text})
        content += [
            {"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in calls
        ]
        return ModelTurn(
            content=content,
            tool_calls=calls,
            text=turn.text,
            usage=turn.usage,
            stop_reason=turn.stop_reason or ("tool_use" if calls else "end_turn"),
            model="fake",
        )


def _as_turn(answer: Any) -> FakeTurn:
    if isinstance(answer, BaseException):
        raise answer
    if isinstance(answer, FakeTurn):
        return answer
    if isinstance(answer, ToolCall):
        return FakeTurn(calls=(answer,))
    if isinstance(answer, str):
        return FakeTurn(text=answer)
    if isinstance(answer, list | tuple):
        return FakeTurn(calls=tuple(answer))
    raise TypeError(f"not a scripted turn: {answer!r}")


FAKE_ROUTING = Routing(version=1, tasks={})


@dataclass
class FakeLLM:
    """Test double. `script` maps a task to its answers, in order.

    - `structured`: each answer is a dict, a model instance, or an exception to raise.
    - `run_agent`: each answer is one model turn: a `ToolCall`, a list of them, a `FakeTurn`,
      a plain string (a text-only turn), or an exception. The turns go through the real loop
      (`llm_gateway.loop`), so budgets, validation and repair behave as in production.

    `calls` records every request; `records` every `llm_call` row the loop logged."""

    script: dict[str, list[Any]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    on_call: Callable[[dict[str, Any]], None] | None = None
    records: list[CallRecord] = field(default_factory=list)

    def structured(
        self,
        task: str,
        *,
        system: str,
        messages: list[Message],
        schema: type[T],
        prompt_version: str,
        timeout_s: float | None = None,
    ) -> T:
        call = {"task": task, "system": system, "messages": messages, "timeout_s": timeout_s}
        self.calls.append(call)
        if self.on_call is not None:
            self.on_call(call)
        answers = self.script.get(task, [])
        if not answers:
            raise LLMUnavailableError(f"FakeLLM has no scripted answer for {task}")
        answer = answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer if isinstance(answer, schema) else schema.model_validate(answer)

    def run_agent(self, spec: AgentSpec[T], *, sink: CallSink | None = None) -> AgentResult[T]:
        def both(record: CallRecord) -> None:
            self.records.append(record)
            if sink is not None:
                sink(record)

        return run_loop(
            spec,
            route=TaskRoute(model="fake", max_tokens=1000),
            routing=FAKE_ROUTING,
            legs=[Leg(_ScriptedBackend(self, spec.task), "fake")],
            sink=both,
        )


_client: Any = UnavailableLLM()


def get_llm() -> LLM:
    """The process-wide client (FastAPI dependency; override it in tests)."""
    client: LLM = _client
    return client


def set_llm(client: LLM) -> None:
    global _client
    _client = client
