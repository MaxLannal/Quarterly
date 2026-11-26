"""Provider backends against stub SDK clients: the request shape the current models need, and
the translation of responses and errors. Nothing here opens a connection."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from llm_gateway.providers import AnthropicBackend, OpenRouterBackend, to_openai_messages
from llm_gateway.types import ModelRequest, ProviderError, ToolSpec


def request(**kw: Any) -> ModelRequest:
    base: dict[str, Any] = {
        "model": "model-from-routing",
        "system": "You are the advisor.",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [ToolSpec("get_course", "d", {"type": "object"}, True)],
        "max_tokens": 4000,
        "effort": "low",
        "timeout_s": 12.0,
    }
    base.update(kw)
    return ModelRequest(**base)


class Block(SimpleNamespace):
    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


class StubAnthropic:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self.timeout: float | None = None
        self.response = response
        self.error = error
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, timeout: float) -> StubAnthropic:
        self.timeout = timeout
        return self

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def anthropic_response() -> Any:
    return SimpleNamespace(
        content=[
            Block(type="thinking", thinking="", signature="sig"),
            Block(type="text", text="Looking it up."),
            Block(type="tool_use", id="toolu_1", name="get_course", input={"code": "MATH 20700"}),
        ],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=100,
            cache_creation_input_tokens=None,
        ),
        stop_reason="tool_use",
        model="model-from-routing",
    )


def test_anthropic_request_shape_for_current_models() -> None:
    stub = StubAnthropic(anthropic_response())
    turn = AnthropicBackend("k", client=stub).complete(request())
    kw = stub.kwargs
    assert kw["model"] == "model-from-routing" and stub.timeout == 12.0
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["tool_choice"] == {"type": "auto"}
    assert kw["tools"][0]["strict"] is True
    assert kw["output_config"] == {"effort": "low"}
    for banned in ("thinking", "temperature", "top_p", "top_k", "fallbacks"):
        assert banned not in kw
    # Thinking blocks are kept, unchanged, for the next request.
    assert turn.content[0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    assert turn.tool_calls[0].input == {"code": "MATH 20700"}
    assert turn.text == "Looking it up."
    assert turn.usage.cache_read_tokens == 100 and turn.usage.cache_write_tokens == 0


def test_anthropic_refusal_fallback_uses_the_beta_parameter() -> None:
    stub = StubAnthropic(anthropic_response())
    AnthropicBackend("k", client=stub).complete(request(refusal_fallback=True, effort=None))
    assert stub.kwargs["fallbacks"] == "default"
    assert stub.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert "output_config" not in stub.kwargs


def _status(cls: type[Exception], code: int) -> Exception:
    req = httpx2.Request("POST", "https://example.invalid/v1/messages")
    resp = httpx2.Response(code, request=req)
    return cls("err", response=resp, body=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("error", "fatal"),
    [
        (_status(anthropic.InternalServerError, 529), False),
        (_status(anthropic.RateLimitError, 429), False),
        (_status(anthropic.BadRequestError, 400), True),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x.invalid")), False),
    ],
)
def test_anthropic_errors_become_provider_errors(error: Exception, fatal: bool) -> None:
    with pytest.raises(ProviderError) as err:
        AnthropicBackend("k", client=StubAnthropic(error=error)).complete(request())
    assert err.value.fatal is fatal


def test_history_translates_to_openai_messages() -> None:
    history = [
        {"role": "user", "content": "Which is lighter?"},
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "", "signature": "s"},
                {"type": "text", "text": "Checking."},
                {"type": "tool_use", "id": "t1", "name": "get_course", "input": {"code": "A 1"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "{}", "is_error": True},
                {"type": "text", "text": "Finish now."},
            ],
        },
    ]
    out = to_openai_messages("sys", history)
    assert out[0]["role"] == "system"
    assert out[1] == {"role": "user", "content": "Which is lighter?"}
    assert out[2]["content"] == "Checking." and out[2]["tool_calls"][0]["id"] == "t1"
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "ERROR: {}"}
    assert out[4] == {"role": "user", "content": "Finish now."}


class StubOpenAI:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self.response = response
        self.error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, timeout: float) -> StubOpenAI:
        return self

    def _create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def test_openrouter_backend_round_trip() -> None:
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="c1",
                function=SimpleNamespace(name="get_course", arguments='{"code": "A 1"}'),
            )
        ],
    )
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason="tool_calls")],
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
        model="fallback-model",
    )
    stub = StubOpenAI(response)
    turn = OpenRouterBackend("k", client=stub).complete(request())
    assert stub.kwargs["tool_choice"] == "auto"
    assert stub.kwargs["tools"][0]["function"]["name"] == "get_course"
    assert turn.stop_reason == "tool_use" and turn.tool_calls[0].input == {"code": "A 1"}
    assert turn.content == [
        {"type": "tool_use", "id": "c1", "name": "get_course", "input": {"code": "A 1"}}
    ]
    assert turn.usage.input_tokens == 7


def test_openrouter_errors_become_provider_errors() -> None:
    req = httpx2.Request("POST", "https://x.invalid")
    error = openai.APIConnectionError(request=req)  # type: ignore[arg-type]
    with pytest.raises(ProviderError):
        OpenRouterBackend("k", client=StubOpenAI(error=error)).complete(request())


def test_anthropic_backend_passes_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_client(**kw: Any) -> object:
        seen.update(kw)
        return object()

    monkeypatch.setattr(anthropic, "Anthropic", fake_client)
    AnthropicBackend("k", base_url="https://api.teamorouter.com")
    assert seen == {"api_key": "k", "max_retries": 0, "base_url": "https://api.teamorouter.com"}


def test_anthropic_backend_no_base_url_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_client(**kw: Any) -> object:
        seen.update(kw)
        return object()

    monkeypatch.setattr(anthropic, "Anthropic", fake_client)
    AnthropicBackend("k")
    assert "base_url" not in seen  # the SDK's own ANTHROPIC_BASE_URL lookup still applies
