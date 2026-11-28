"""The real client behind `llm_gateway.api.LLM`: routing from `llm_routing.yaml`, the
Anthropic SDK with OpenRouter as fallback, budgets, validation and `llm_call` logging.

Built only when API keys are configured (`build_gateway`); tests never construct it with
real providers.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from llm_gateway.loop import Backend, legs_for, run_loop
from llm_gateway.providers import AnthropicBackend, OpenRouterBackend
from llm_gateway.routing import Routing, load_routing
from llm_gateway.types import (
    AgentResult,
    AgentSpec,
    Budget,
    CallRecord,
    CallSink,
    Message,
    SubmitTool,
)

logger = logging.getLogger("llm_gateway")

STRUCTURED_SUBMIT = "submit"


def log_sink(record: CallRecord) -> None:
    """Default sink: the application log (no user identifier in a record)."""
    logger.info(
        "llm_call task=%s model=%s prompt=%s in=%d out=%d cost=%.6f ms=%d ok=%s",
        record.task,
        record.model,
        record.prompt_version,
        record.in_tokens,
        record.out_tokens,
        record.cost_usd,
        record.latency_ms,
        record.ok,
    )


def structured_spec[T: BaseModel](
    task: str,
    *,
    system: str,
    messages: list[Message],
    schema: type[T],
    prompt_version: str,
    timeout_s: float | None,
    max_tokens: int,
) -> AgentSpec[T]:
    """A one-shot structured answer as a run with no tools: the model calls `submit`."""
    return AgentSpec(
        task=task,
        prompt_version=prompt_version,
        system=system
        + f"\n\nGive your answer by calling the `{STRUCTURED_SUBMIT}` tool. Do not answer in "
        "plain text.",
        messages=messages,
        submit=SubmitTool(
            name=STRUCTURED_SUBMIT,
            description="Submit your answer.",
            model=schema,
        ),
        tools=[],
        budget=Budget(tool_calls=0, tokens=max(8 * max_tokens, 20_000), seconds=timeout_s or 30.0),
    )


class Gateway:
    def __init__(
        self,
        routing: Routing,
        *,
        primary: Backend | None,
        fallback: Backend | None,
        sink: CallSink = log_sink,
    ) -> None:
        self.routing = routing
        self.primary = primary
        self.fallback = fallback
        self.sink = sink

    def run_agent[T: BaseModel](
        self, spec: AgentSpec[T], *, sink: CallSink | None = None
    ) -> AgentResult[T]:
        route = self.routing.route(spec.task)
        return run_loop(
            spec,
            route=route,
            routing=self.routing,
            legs=legs_for(route, self.primary, self.fallback),
            sink=sink or self.sink,
        )

    def structured[T: BaseModel](
        self,
        task: str,
        *,
        system: str,
        messages: list[Message],
        schema: type[T],
        prompt_version: str,
        timeout_s: float | None = None,
        sink: CallSink | None = None,
    ) -> T:
        spec = structured_spec(
            task,
            system=system,
            messages=messages,
            schema=schema,
            prompt_version=prompt_version,
            timeout_s=timeout_s,
            max_tokens=self.routing.route(task).max_tokens,
        )
        return self.run_agent(spec, sink=sink).output


def build_gateway(
    *,
    anthropic_api_key: str,
    openrouter_api_key: str,
    anthropic_base_url: str | None = None,
    sink: CallSink = log_sink,
    routing: Routing | None = None,
) -> Gateway | None:
    """The configured gateway, or None when neither provider has a key."""
    if not anthropic_api_key and not openrouter_api_key:
        return None
    routing = routing or load_routing()
    primary: Any = (
        AnthropicBackend(anthropic_api_key, base_url=anthropic_base_url)
        if anthropic_api_key
        else None
    )
    fallback: Any = (
        OpenRouterBackend(openrouter_api_key)
        if openrouter_api_key and routing.providers.fallback == "openrouter"
        else None
    )
    return Gateway(routing, primary=primary, fallback=fallback, sink=sink)
