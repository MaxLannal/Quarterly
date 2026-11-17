"""The agent loop every harness shares (SPEC "Rules every harness follows").

Messages API with tools; the run ends when the model calls its `submit_*` tool with a payload
that validates (one repair turn with the validation error is allowed), or fails with
`AgentError` when a budget runs out, the model declines, or the providers keep failing. The
caller then takes its fallback path.

Provider fallback: errors are counted per run. After `fallback_after_errors` errors on the
primary provider (a fatal 4xx counts as all of them at once), the rest of the run goes to the
fallback provider; the same count there ends the run.

The loop is the same for the real gateway and for `FakeLLM`, so tests exercise it as is.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from llm_gateway.routing import Routing, TaskRoute
from llm_gateway.types import (
    AgentError,
    AgentResult,
    AgentSpec,
    CallRecord,
    CallSink,
    ModelRequest,
    ModelTurn,
    ProviderError,
    SubmitTool,
    Tool,
    ToolCall,
    ToolOutput,
    ToolSpec,
)

logger = logging.getLogger("llm_gateway")

#: Longest tool result handed back to the model, in characters.
MAX_TOOL_RESULT = 12_000


class Backend:
    """One provider. `complete` raises `ProviderError` on any provider failure."""

    name = "backend"

    def complete(self, request: ModelRequest) -> ModelTurn:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class Leg:
    """A provider and the model it serves for this task."""

    backend: Backend
    model: str


def legs_for(route: TaskRoute, primary: Backend | None, fallback: Backend | None) -> list[Leg]:
    legs = []
    if primary is not None:
        legs.append(Leg(primary, route.model))
    if fallback is not None and route.fallback is not None:
        legs.append(Leg(fallback, route.fallback.model))
    return legs


def submit_schema(submit: SubmitTool[Any]) -> dict[str, Any]:
    return submit.input_schema or submit.model.model_json_schema()


def _tool_specs(tools: Sequence[Tool], submit: SubmitTool[Any]) -> list[ToolSpec]:
    specs = [ToolSpec(t.name, t.description, t.input_schema, t.strict) for t in tools]
    specs.append(ToolSpec(submit.name, submit.description, submit_schema(submit), submit.strict))
    return specs


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors()[:8]:
            where = ".".join(str(p) for p in err["loc"]) or "(payload)"
            parts.append(f"{where}: {err['msg']}")
        return "; ".join(parts)
    return str(exc)


def _clip(text: str) -> str:
    return text if len(text) <= MAX_TOOL_RESULT else text[:MAX_TOOL_RESULT] + " [truncated]"


def run_loop[T: BaseModel](
    spec: AgentSpec[T],
    *,
    route: TaskRoute,
    routing: Routing,
    legs: list[Leg],
    sink: CallSink | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> AgentResult[T]:
    if not legs:
        raise AgentError("unavailable", f"no provider configured for {spec.task}")
    start = clock()
    budget = spec.budget
    handlers = {t.name: t for t in spec.tools}
    specs = _tool_specs(spec.tools, spec.submit)
    messages: list[dict[str, Any]] = [{"role": m.role, "content": m.content} for m in spec.messages]
    seen: set[str] = set(spec.known_ids)
    calls: list[ToolCall] = []
    tokens = 0
    cost = 0.0
    repaired = False
    leg_index = 0
    errors = 0
    used_tools = 0
    model = legs[0].model

    def record(rec: CallRecord) -> None:
        if sink is not None:
            try:
                sink(rec)
            except Exception:  # logging must never break a run
                logger.exception("llm_call sink failed")

    while True:
        remaining = budget.seconds - (clock() - start)
        if remaining <= 0:
            raise AgentError("budget_seconds", f"{spec.task} ran out of time")
        leg = legs[leg_index]
        request = ModelRequest(
            model=leg.model,
            system=spec.system,
            messages=list(messages),
            tools=specs,
            max_tokens=min(route.max_tokens, spec.max_tokens or route.max_tokens),
            effort=route.effort,
            timeout_s=remaining,
            refusal_fallback=route.refusal_fallback,
            thinking=route.thinking,
        )
        began = clock()
        try:
            turn = leg.backend.complete(request)
        except ProviderError as exc:
            record(
                CallRecord(
                    spec.task,
                    leg.model,
                    spec.prompt_version,
                    0,
                    0,
                    0.0,
                    int((clock() - began) * 1000),
                    False,
                )
            )
            errors += routing.providers.fallback_after_errors if exc.fatal else 1
            logger.warning("%s: %s error (%s)", spec.task, leg.backend.name, type(exc).__name__)
            if errors >= routing.providers.fallback_after_errors:
                leg_index += 1
                errors = 0
                if leg_index >= len(legs):
                    raise AgentError("provider", f"{spec.task}: every provider failed") from exc
            continue
        model = turn.model or leg.model
        call_cost = routing.cost(leg.model, turn.usage)
        cost += call_cost
        tokens += turn.usage.total
        record(
            CallRecord(
                task=spec.task,
                model=model,
                prompt_version=spec.prompt_version,
                in_tokens=turn.usage.input_tokens
                + turn.usage.cache_read_tokens
                + turn.usage.cache_write_tokens,
                out_tokens=turn.usage.output_tokens,
                cost_usd=call_cost,
                latency_ms=int((clock() - began) * 1000),
                ok=turn.stop_reason != "refusal",
            )
        )
        if turn.stop_reason == "refusal":
            raise AgentError("refusal", f"{spec.task}: the model declined")
        if turn.stop_reason == "max_tokens":
            # A tool call cut off by the output limit arrives with partial or empty input; running
            # it only makes the model try again and be cut off again (live, 2026-11-16).
            logger.warning("%s: reply cut off at max_tokens", spec.task)
            raise AgentError("truncated", f"{spec.task}: the reply hit max_tokens")
        if tokens > budget.tokens:
            raise AgentError("budget_tokens", f"{spec.task} used {tokens} tokens")
        messages.append({"role": "assistant", "content": turn.content})

        if not turn.tool_calls:
            if repaired:
                raise AgentError("invalid_output", f"{spec.task}: no {spec.submit.name} call")
            repaired = True
            messages.append(
                {
                    "role": "user",
                    "content": f"Finish by calling the `{spec.submit.name}` tool with your "
                    "answer. Do not answer in plain text.",
                }
            )
            continue

        results: list[dict[str, Any]] = []
        submitted: T | None = None
        for call in turn.tool_calls:
            calls.append(call)
            if call.name == spec.submit.name:
                try:
                    payload = spec.submit.model.model_validate(call.input)
                    if spec.submit.check is not None:
                        spec.submit.check(payload)
                except (ValidationError, ValueError) as exc:
                    if repaired:
                        raise AgentError(
                            "invalid_output", f"{spec.task}: {_validation_message(exc)}"
                        ) from exc
                    repaired = True
                    results.append(
                        _result(
                            call,
                            ToolOutput(
                                "Your submission is invalid: "
                                + _validation_message(exc)
                                + f". Fix it and call `{spec.submit.name}` again.",
                                is_error=True,
                            ),
                        )
                    )
                    continue
                submitted = payload
                break
            used_tools += 1
            if used_tools > budget.tool_calls:
                raise AgentError("budget_tool_calls", f"{spec.task} used {used_tools} tool calls")
            tool = handlers.get(call.name)
            if tool is None:
                out = ToolOutput(f"Unknown tool `{call.name}`.", is_error=True)
            else:
                try:
                    out = tool.handler(call.input)
                except Exception as exc:  # a tool error goes back to the model, not the user
                    logger.warning("%s: tool %s failed (%s)", spec.task, call.name, exc)
                    out = ToolOutput(f"The tool failed: {exc}", is_error=True)
            seen |= out.ids
            results.append(_result(call, out))
        if submitted is not None:
            return AgentResult(
                output=submitted,
                seen_ids=seen,
                tool_calls=calls,
                tokens=tokens,
                cost_usd=cost,
                model=model,
            )
        messages.append({"role": "user", "content": results})


def _result(call: ToolCall, out: ToolOutput) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": call.id,
        "content": _clip(out.content),
    }
    if out.is_error:
        block["is_error"] = True
    return block


def to_json(data: Any) -> str:
    """Compact, stable JSON for tool results (sorted keys keep prompt caching effective)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
