"""Live agent tests under a hard budget (claude-code-prompts/13-live-agent-test.md): the
LiveBudgetGuard, the spend ledger, response recordings and replay.

- `Ledger`: append-only JSON lines (`evals/live/ledger.jsonl`), one line per real provider
  call: time, test id, phase, task, provider, model, input / output / cache-write /
  cache-read tokens, cost in USD, latency. The ledger is the source of truth: a restarted run
  starts from what earlier runs spent.
- `LiveBudgetGuard`: before every call it prices the worst case (input estimated as
  characters / 3 at the dearer of the input and cache-write prices, plus `max_tokens` of
  output) and refuses the call, before it is sent, if that could take the total past the run
  cap ($4.50) or the phase past its cap. After one refusal every later call is refused.
  After each call it charges the actual cost from the response's `usage`.
- `GuardedGateway`: a `Gateway` whose provider calls all go through the guard and the
  recorder.
- `Recorder`: every request/answer pair of a test goes to `<root>/<test id>.json`. Requests
  hold the request body only (system, messages, tool names), never a key or a header;
  `secrets_in` checks the folder for keys and auth headers.
- `ReplayBackend` / `replay_gateway` (ReplayLLM): serve a test's recorded answers in order,
  so every live test re-runs free and every bug found live becomes a regression test.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm_gateway.gateway import Gateway
from llm_gateway.loop import Backend
from llm_gateway.routing import Routing
from llm_gateway.types import (
    AgentResult,
    AgentSpec,
    CallRecord,
    CallSink,
    LLMUnavailableError,
    ModelRequest,
    ModelTurn,
    ProviderError,
    ToolCall,
    Usage,
)

#: The whole live-test budget (prompt 13, rule 1; the Console's $5 limit is the backstop).
TOTAL_CAP_USD = 4.50
#: Prompt 13, rule 3.
PHASE_CAPS_USD = {
    "phase0": 0.10,
    "phase1": 1.80,
    "phase2": 0.40,
    "phase3": 1.40,
    "phase4": 0.30,
    "phase5": 0.50,
}
#: Characters per token for the worst-case input estimate (prompt 13, rule 2).
CHARS_PER_TOKEN = 3.0
#: Allowance per request for the provider's tool-use preamble and message framing.
OVERHEAD_TOKENS = 600


class BudgetExceeded(LLMUnavailableError):  # noqa: N818 (reads as a sentence at call sites)
    """The guard refused a live call. The run must make no more live calls."""


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------- ledger


@dataclass(frozen=True)
class LedgerEntry:
    time: str
    test_id: str
    phase: str
    task: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_usd: float
    latency_ms: int
    ok: bool


@dataclass
class Ledger:
    path: Path

    def entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        return [
            LedgerEntry(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def total(self) -> float:
        return round(sum(e.cost_usd for e in self.entries()), 6)

    def phase_total(self, phase: str) -> float:
        return round(sum(e.cost_usd for e in self.entries() if e.phase == phase), 6)

    def test_total(self, test_id: str) -> float:
        return round(sum(e.cost_usd for e in self.entries() if e.test_id == test_id), 6)

    def append(self, entry: LedgerEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), sort_keys=True) + "\n")


# -------------------------------------------------------------------------------- guard


def request_chars(request: ModelRequest) -> int:
    """Characters the provider will read: system, messages and tool schemas."""
    tools = [
        {"name": t.name, "description": t.description, "schema": t.input_schema}
        for t in request.tools
    ]
    return (
        len(request.system)
        + len(json.dumps(request.messages, default=str))
        + len(json.dumps(tools))
    )


def worst_case_usd(routing: Routing, model: str, request: ModelRequest) -> float:
    """The most this request can cost. A model without a list price cannot be bounded, so it
    costs infinity (refused)."""
    price = routing.prices.get(model)
    if price is None:
        return math.inf
    input_tokens = math.ceil(request_chars(request) / CHARS_PER_TOKEN) + OVERHEAD_TOKENS
    per_input = max(price.input, price.cache_write)  # a cache write costs more than input
    return (input_tokens * per_input + request.max_tokens * price.output) / 1_000_000


@dataclass
class LiveBudgetGuard:
    ledger: Ledger
    routing: Routing
    phase_caps: dict[str, float]
    total_cap_usd: float = TOTAL_CAP_USD
    phase: str = ""
    test_id: str = ""
    #: The task of the run in flight (set by `GuardedGateway`).
    task: str = ""
    refused: bool = False
    refusal: str = ""

    @contextmanager
    def running(self, phase: str, test_id: str) -> Iterator[None]:
        """Calls inside the block are charged to `phase` / `test_id`."""
        before = (self.phase, self.test_id)
        self.phase, self.test_id = phase, test_id
        try:
            yield
        finally:
            self.phase, self.test_id = before

    def spent(self) -> float:
        return self.ledger.total()

    def check(self, model: str, request: ModelRequest) -> float:
        """Raise `BudgetExceeded` unless this call's worst case fits both caps."""
        if self.refused:
            raise BudgetExceeded(f"live calls stopped earlier: {self.refusal}")
        if self.phase not in self.phase_caps:
            self._refuse(f"no budget phase is set for this call (phase {self.phase!r})")
        worst = worst_case_usd(self.routing, model, request)
        total, in_phase = self.ledger.total(), self.ledger.phase_total(self.phase)
        if total + worst > self.total_cap_usd:
            self._refuse(
                f"{model}: worst case ${worst:.4f} on top of ${total:.4f} spent passes the "
                f"${self.total_cap_usd:.2f} total cap"
            )
        cap = self.phase_caps[self.phase]
        if in_phase + worst > cap:
            self._refuse(
                f"{model}: worst case ${worst:.4f} on top of ${in_phase:.4f} spent in "
                f"{self.phase} passes its ${cap:.2f} cap"
            )
        return worst

    def _refuse(self, why: str) -> None:
        self.refused, self.refusal = True, why
        raise BudgetExceeded(why)

    def charge(
        self, provider: str, model: str, usage: Usage, ok: bool, latency_ms: int = 0
    ) -> float:
        cost = self.routing.cost(model, usage)
        self.ledger.append(
            LedgerEntry(
                time=now(),
                test_id=self.test_id,
                phase=self.phase,
                task=self.task,
                provider=provider,
                model=model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cost_usd=round(cost, 8),
                latency_ms=latency_ms,
                ok=ok,
            )
        )
        return cost


# ---------------------------------------------------------------------------- recordings


def turn_to_json(turn: ModelTurn) -> dict[str, Any]:
    return {
        "content": turn.content,
        "tool_calls": [{"name": c.name, "input": c.input, "id": c.id} for c in turn.tool_calls],
        "text": turn.text,
        "usage": asdict(turn.usage),
        "stop_reason": turn.stop_reason,
        "model": turn.model,
    }


def turn_from_json(data: dict[str, Any]) -> ModelTurn:
    return ModelTurn(
        content=data["content"],
        tool_calls=[ToolCall(c["name"], c["input"], c["id"]) for c in data["tool_calls"]],
        text=data["text"],
        usage=Usage(**data["usage"]),
        stop_reason=data["stop_reason"],
        model=data["model"],
    )


@dataclass
class Recorder:
    """Appends each request/answer pair of a test to `<root>/<test id>.json`."""

    root: Path

    def path(self, test_id: str) -> Path:
        return self.root / f"{re.sub(r'[^A-Za-z0-9._-]', '_', test_id)}.json"

    def save(self, test_id: str, request: ModelRequest, turn: ModelTurn) -> Path:
        out = self.path(test_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        pairs = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
        pairs.append(
            {
                "request": {
                    "model": request.model,
                    "system": request.system,
                    "messages": request.messages,
                    "tools": [t.name for t in request.tools],
                    "max_tokens": request.max_tokens,
                    "effort": request.effort,
                },
                "response": turn_to_json(turn),
            }
        )
        out.write_text(json.dumps(pairs, indent=1, default=str), encoding="utf-8")
        return out


#: Shapes of credentials and auth headers that must never be in a recording or the ledger.
SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk-or-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\b(x-api-key|authorization)\b\s*[:=]"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{12,}"),
)


def secrets_in(paths: Iterable[Path], known: Iterable[str] = ()) -> list[str]:
    """Files (with the reason) that hold a key, an auth header or one of the `known` secret
    values. The values themselves are never returned or printed."""
    values = [k for k in known if len(k) >= 8]
    found = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(v in text for v in values):
            found.append(f"{path.name}: contains a configured API key")
        found += [
            f"{path.name}: matches {p.pattern[:20]}" for p in SECRET_PATTERNS if p.search(text)
        ]
    return found


# ------------------------------------------------------------------------ guarded gateway


class GuardedBackend(Backend):
    """A real provider behind the guard, the ledger and the recorder."""

    def __init__(self, inner: Backend, guard: LiveBudgetGuard, recorder: Recorder | None) -> None:
        self.inner = inner
        self.guard = guard
        self.recorder = recorder
        self.name = f"guarded-{inner.name}"

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.guard.check(request.model, request)
        began = time.monotonic()
        try:
            turn = self.inner.complete(request)
        except ProviderError:
            # A failed request is not billed; it is logged at zero cost.
            latency = int((time.monotonic() - began) * 1000)
            self.guard.charge(self.inner.name, request.model, Usage(), ok=False, latency_ms=latency)
            raise
        latency = int((time.monotonic() - began) * 1000)
        self.guard.charge(self.inner.name, request.model, turn.usage, ok=True, latency_ms=latency)
        if self.recorder is not None:
            self.recorder.save(self.guard.test_id, request, turn)
        return turn


class GuardedGateway(Gateway):
    """A `Gateway` whose provider calls all go through the guard (and the recorder); it tells
    the guard which task each run is for, for the ledger."""

    def __init__(
        self,
        routing: Routing,
        *,
        primary: Backend | None,
        fallback: Backend | None,
        guard: LiveBudgetGuard,
        recorder: Recorder | None,
    ) -> None:
        def wrap(backend: Backend | None) -> Backend | None:
            return GuardedBackend(backend, guard, recorder) if backend is not None else None

        super().__init__(routing, primary=wrap(primary), fallback=wrap(fallback), sink=_no_sink)
        self.guard = guard

    def run_agent[T: BaseModel](
        self, spec: AgentSpec[T], *, sink: CallSink | None = None
    ) -> AgentResult[T]:
        before = self.guard.task
        self.guard.task = spec.task
        try:
            return super().run_agent(spec, sink=sink)
        finally:
            self.guard.task = before


def _no_sink(record: CallRecord) -> None:
    """The ledger is the record of live calls."""


# -------------------------------------------------------------------------------- replay


class ReplayBackend(Backend):
    """Serves the recorded answers of one test, in order. No network."""

    name = "replay"

    def __init__(self, recording: Path) -> None:
        pairs = json.loads(recording.read_text(encoding="utf-8"))
        self.turns = [turn_from_json(p["response"]) for p in pairs]
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.requests.append(request)
        if not self.turns:
            raise ProviderError("the recording has no more answers", fatal=True)
        return self.turns.pop(0)


def replay_gateway(routing: Routing, recording: Path) -> Gateway:
    """ReplayLLM: a gateway that answers from one test's recording."""
    return Gateway(routing, primary=ReplayBackend(recording), fallback=None, sink=_no_sink)
