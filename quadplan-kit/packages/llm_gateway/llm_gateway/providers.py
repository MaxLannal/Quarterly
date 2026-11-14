"""Provider backends: the Anthropic SDK (primary) and OpenRouter through its
OpenAI-compatible API (fallback). Both take an Anthropic-format request and return a
`ModelTurn`; neither retries (the loop counts errors and switches provider).

Request shape for the current models (Opus 5.5, Sonnet 5.5, Haiku 5.5): no `thinking`
parameter (adaptive thinking is the default and cannot be disabled on Opus 5.5), effort in
`output_config`, `tool_choice` auto (forced tool choice is rejected), strict tools, no
sampling parameters and no assistant prefill. The system prompt and tool list are cached
(`cache_control` on the system block covers tools + system), and top-level automatic caching
covers the growing conversation of a tool loop.
"""

from __future__ import annotations

import json
from typing import Any, cast

from llm_gateway.loop import Backend
from llm_gateway.types import ModelRequest, ModelTurn, ProviderError, ToolCall, ToolSpec, Usage

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _anthropic_tool(spec: ToolSpec) -> dict[str, Any]:
    tool: dict[str, Any] = {
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_schema,
    }
    if spec.strict:
        tool["strict"] = True
    return tool


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        self._client = client

    def complete(self, request: ModelRequest) -> ModelTurn:
        import anthropic

        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": request.system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": request.messages,
            "cache_control": {"type": "ephemeral"},
        }
        if request.tools:
            kwargs["tools"] = [_anthropic_tool(t) for t in request.tools]
            kwargs["tool_choice"] = {"type": "auto"}
        if request.effort is not None:
            kwargs["output_config"] = {"effort": request.effort}
        client = self._client.with_options(timeout=max(1.0, request.timeout_s))
        try:
            if request.refusal_fallback:
                response = client.beta.messages.create(
                    betas=[REFUSAL_FALLBACK_BETA], fallbacks="default", **kwargs
                )
            else:
                response = client.messages.create(**kwargs)
        except anthropic.RateLimitError as exc:
            raise ProviderError("rate limited") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"status {exc.status_code}", fatal=exc.status_code < 500) from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            raise ProviderError("connection") from exc
        return _anthropic_turn(response)


def _anthropic_turn(response: Any) -> ModelTurn:
    content: list[dict[str, Any]] = []
    calls: list[ToolCall] = []
    texts: list[str] = []
    for block in response.content:
        content.append(cast(dict[str, Any], block.to_dict()))
        if block.type == "tool_use":
            raw = block.input
            calls.append(
                ToolCall(block.name, raw if isinstance(raw, dict) else json.loads(raw), block.id)
            )
        elif block.type == "text":
            texts.append(block.text)
    u = response.usage
    usage = Usage(
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", None) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", None) or 0,
    )
    return ModelTurn(
        content=content,
        tool_calls=calls,
        text="".join(texts),
        usage=usage,
        stop_reason=str(response.stop_reason or ""),
        model=str(response.model or ""),
    )


# --------------------------------------------------------------------------- OpenRouter


def to_openai_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic-format history -> OpenAI chat messages. Thinking blocks are dropped (they
    belong to the provider that wrote them)."""
    out: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        }
    ]
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        if message["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                }
                for b in content
                if b.get("type") == "tool_use"
            ]
            entry: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
            continue
        texts = []
        for b in content:
            if b.get("type") == "tool_result":
                body = b.get("content", "")
                if b.get("is_error"):
                    body = f"ERROR: {body}"
                out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": body})
            elif b.get("type") == "text":
                texts.append(b["text"])
        if texts:
            out.append({"role": "user", "content": "\n".join(texts)})
    return out


class OpenRouterBackend(Backend):
    name = "openrouter"

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if client is None:
            import openai

            client = openai.OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, max_retries=0)
        self._client = client

    def complete(self, request: ModelRequest) -> ModelTurn:
        import openai

        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": to_openai_messages(request.system, request.messages),
        }
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]
            kwargs["tool_choice"] = "auto"
        if request.effort is not None:
            kwargs["extra_body"] = {"reasoning": {"effort": request.effort}}
        client = self._client.with_options(timeout=max(1.0, request.timeout_s))
        try:
            response = client.chat.completions.create(**kwargs)
        except openai.RateLimitError as exc:
            raise ProviderError("rate limited") from exc
        except openai.APIStatusError as exc:
            raise ProviderError(f"status {exc.status_code}", fatal=exc.status_code < 500) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("connection") from exc
        if not response.choices:
            raise ProviderError("empty response")
        choice = response.choices[0]
        message = choice.message
        content: list[dict[str, Any]] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        calls: list[ToolCall] = []
        for tc in message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(tc.function.name, args, tc.id))
            content.append(
                {"type": "tool_use", "id": tc.id, "name": tc.function.name, "input": args}
            )
        u = response.usage
        usage = Usage(
            input_tokens=(u.prompt_tokens if u else 0) or 0,
            output_tokens=(u.completion_tokens if u else 0) or 0,
        )
        stop = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens"}.get(
            str(choice.finish_reason), str(choice.finish_reason)
        )
        return ModelTurn(
            content=content,
            tool_calls=calls,
            text=message.content or "",
            usage=usage,
            stop_reason=stop,
            model=str(response.model or request.model),
        )
