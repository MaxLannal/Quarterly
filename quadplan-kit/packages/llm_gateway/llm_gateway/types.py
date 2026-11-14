"""Value types shared by the gateway, its backends and its callers.

A *run* is one agent harness execution (SPEC "Rules every harness follows"): a Messages-API
loop with a fixed tool list, a budget, and a `submit_*` tool whose payload is validated with
Pydantic (one repair turn). Nothing here talks to a provider.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel


class LLMUnavailableError(RuntimeError):
    """No client is configured, the provider failed, or the time budget ran out. Every
    caller has a fallback path for it (SPEC "Rules every harness follows")."""


FailureReason = Literal[
    "unavailable",  # no client configured
    "provider",  # the provider (and its fallback) kept failing
    "refusal",  # the model declined
    "invalid_output",  # the submit payload failed validation twice
    "budget_tool_calls",
    "budget_tokens",
    "budget_seconds",
]


class AgentError(LLMUnavailableError):
    """A run ended without a valid `submit_*` payload. `reason` says why; the caller takes
    its fallback path."""

    def __init__(self, reason: FailureReason, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason: FailureReason = reason
        self.detail = detail


@dataclass(frozen=True)
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Budget:
    """Per-run limits; exceeding any one ends the run with `AgentError` (the fallback)."""

    tool_calls: int = 12
    tokens: int = 60_000  # input + output, summed over every model call of the run
    seconds: float = 60.0


@dataclass(frozen=True)
class ToolCall:
    name: str
    input: dict[str, Any]
    id: str = ""


@dataclass(frozen=True)
class ToolOutput:
    """What a tool returns to the model. `ids` are the citable ids this result contains
    (`kind:id`, e.g. `course:MATH 20700`); a run may only cite ids some tool returned."""

    content: str
    ids: frozenset[str] = frozenset()
    is_error: bool = False


ToolHandler = Callable[[dict[str, Any]], ToolOutput]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    #: Strict tool use: the provider guarantees the input matches the schema. The schema must
    #: set `additionalProperties: false` and list every property in `required`.
    strict: bool = True


@dataclass(frozen=True)
class SubmitTool[T: BaseModel]:
    """The tool that ends a run. Its input is validated with `model`, then with `check`
    (which raises `ValueError` with a message the model can act on). A failure gets one
    repair turn with the error; a second failure ends the run (`invalid_output`)."""

    name: str
    description: str
    model: type[T]
    input_schema: dict[str, Any] | None = None  # default: model.model_json_schema()
    check: Callable[[T], None] | None = None
    strict: bool = False


@dataclass
class AgentSpec[T: BaseModel]:
    task: str  # a key of llm_routing.yaml
    prompt_version: str
    system: str
    messages: list[Message]
    submit: SubmitTool[T]
    tools: list[Tool] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    #: Ids the caller already handed the model (e.g. the plan's own courses); they count as
    #: returned by a tool for citation checks.
    known_ids: Iterable[str] = ()


@dataclass
class AgentResult[T: BaseModel]:
    output: T
    #: Every id some tool returned in this run, plus `known_ids`.
    seen_ids: set[str]
    tool_calls: list[ToolCall]
    tokens: int
    cost_usd: float
    model: str


# ------------------------------------------------------------------ provider-facing types


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    strict: bool


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    #: Anthropic Messages format (role + content blocks); backends translate as needed.
    messages: list[dict[str, Any]]
    tools: list[ToolSpec]
    max_tokens: int
    effort: str | None
    timeout_s: float
    refusal_fallback: bool = False


@dataclass(frozen=True)
class ModelTurn:
    #: The assistant content blocks in Anthropic format, appended to the history unchanged
    #: (thinking blocks must be passed back as they came).
    content: list[dict[str, Any]]
    tool_calls: list[ToolCall]
    text: str
    usage: Usage
    stop_reason: str
    model: str


class ProviderError(Exception):
    """A provider call failed. `fatal` errors (a 4xx other than 429) are not worth retrying
    on the same provider."""

    def __init__(self, message: str, *, fatal: bool = False) -> None:
        super().__init__(message)
        self.fatal = fatal


@dataclass(frozen=True)
class CallRecord:
    """One row of `llm_call`. No user identifier, by rule."""

    task: str
    model: str
    prompt_version: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    latency_ms: int
    ok: bool


CallSink = Callable[[CallRecord], None]
