"""The contract between the LLM gateway and its callers (set before prompts 07 and 08 ran in
parallel; prompt 07 builds the real client behind it).

Callers ask for a *structured* answer: a Pydantic model validated from the model's output.
`get_llm()` returns the configured client; tests use `FakeLLM`. Nothing here sends a request:
until prompt 07 lands, `get_llm()` returns `UnavailableLLM`, which refuses every call.

Model ids never appear in code: a call names its *task* (a key of `llm_routing.yaml`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMUnavailableError(RuntimeError):
    """No client is configured, the provider failed, or the time budget ran out. Every
    caller has a fallback path for it (SPEC "Rules every harness follows")."""


@dataclass(frozen=True)
class Message:
    role: str  # "user" | "assistant"
    content: str


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


class UnavailableLLM:
    """The default until a real client is configured: refuses every call."""

    def structured(self, task: str, **_: Any) -> Any:
        raise LLMUnavailableError(f"no LLM client is configured (task {task})")


@dataclass
class FakeLLM:
    """Test double. `script` maps a task to the answers it returns, in order (a dict, a model
    instance, or an exception to raise); `calls` records every request."""

    script: dict[str, list[Any]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    on_call: Callable[[dict[str, Any]], None] | None = None

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


_client: LLM = UnavailableLLM()


def get_llm() -> LLM:
    """The process-wide client (FastAPI dependency; override it in tests)."""
    return _client


def set_llm(client: LLM) -> None:
    global _client
    _client = client
