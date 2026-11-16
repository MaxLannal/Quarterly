"""Live agent tests under a hard budget (prompt 13): the LiveBudgetGuard, the spend ledger and
response recordings.

- `Ledger`: an append-only JSON-lines file (`evals/live/ledger.jsonl`), one line per real
  provider call, with its phase, case, task, model, tokens and cost. The ledger, not memory,
  is the source of truth: a new run starts from what earlier runs spent.
- `LiveBudgetGuard`: before every real call it prices the *worst case* (the request's input,
  estimated generously from its characters, plus `max_tokens` of output at the model's list
  price) and refuses the call when that could take the total past `total_cap_usd` or the
  current phase past its cap. After a refusal every later call is refused too.
- `GuardedBackend`: wraps a provider backend: guard check, the call, the ledger line, the
  recording. Nothing here sees or stores an API key; recordings hold the request body and the
  model's answer only.
- `ReplayBackend` / `replay_gateway`: serve a case's recorded turns in order, so a bug found
  live becomes a regression test that makes no API call.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
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

#: The whole live-test budget (Richard, 2026-11-16).
TOTAL_CAP_USD = 4.50
#: Characters per token used to bound a request's input (real text averages 3.5-4; 3 errs high).
CHARS_PER_TOKEN = 3.0
#: Fixed allowance per request for the system's tool-use preamble and message framing.
OVERHEAD_TOKENS = 600


class BudgetExceeded(LLMUnavailableError):  # noqa: N818 (reads as a sentence at call sites)
    """The guard refused a live call. The run must make no more live calls."""


def today() -> str:
    return dt.date.today().isoformat()


# ------------------------------------------------------------------------------- ledger


@dataclass(frozen=True)
class LedgerEntry:
    day: str
    phase: str
    case: str
    task: str
    provider: str
    model: str
    in_tokens: int
    out_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    ok: bool


@dataclass
class Ledger:
    path: Path

    def entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(LedgerEntry(**json.loads(line)))
        return rows

    def total(self) -> float:
        return round(sum(e.cost_usd for e in self.entries()), 6)

    def phase_total(self, phase: str) -> float:
        return round(sum(e.cost_usd for e in self.entries() if e.phase == phase), 6)

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
    """The most this request can cost: generous input estimate plus every allowed output
    token. A model without a list price cannot be bounded, so it costs infinity (refused)."""
    price = routing.prices.get(model)
    if price is None:
        return math.inf
    input_tokens = math.ceil(request_chars(request) / CHARS_PER_TOKEN) + OVERHEAD_TOKENS
    # A cache write costs more than plain input, so price the whole input at the higher rate.
    per_input = max(price.input, price.cache_write)
    return (input_tokens * per_input + request.max_tokens * price.output) / 1_000_000


@dataclass
class LiveBudgetGuard:
    ledger: Ledger
    routing: Routing
    phase_caps: dict[str, float]
    total_cap_usd: float = TOTAL_CAP_USD
    phase: str = ""
    case: str = ""
    #: The task of the run in flight (set by `GuardedGateway`).
    task: str = ""
    refused: bool = False
    refusal: str = ""

    @contextmanager
    def running(self, phase: str, case: str) -> Iterator[None]:
        """Calls inside the block are charged to `phase` / `case`."""
        before = (self.phase, self.case)
        self.phase, self.case = phase, case
        try:
            yield
        finally:
            self.phase, self.case = before

    def spent(self) -> float:
        return self.ledger.total()

    def check(self, model: str, request: ModelRequest) -> float:
        """Raise `BudgetExceeded` unless the worst case of this call fits both caps; returns
        the worst case."""
        if self.refused:
            raise BudgetExceeded(f"live calls stopped earlier: {self.refusal}")
        if not self.phase or self.phase not in self.phase_caps:
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

    def charge(self, provider: str, model: str, usage: Usage, ok: bool) -> float:
        cost = self.routing.cost(model, usage)
        self.ledger.append(
            LedgerEntry(
                day=today(),
                phase=self.phase,
                case=self.case,
                task=self.task,
                provider=provider,
                model=model,
                in_tokens=usage.input_tokens,
                out_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=round(cost, 6),
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
    """Writes `<root>/<phase>/<case>/NNN.json`: the request body and the model's turn."""

    root: Path
    counters: dict[tuple[str, str], int] = field(default_factory=dict)

    def save(self, phase: str, case: str, request: ModelRequest, turn: ModelTurn) -> Path:
        key = (phase, case)
        self.counters[key] = n = self.counters.get(key, 0) + 1
        folder = self.root / phase / case
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{n:03d}.json"
        body = {
            "request": {
                "model": request.model,
                "system": request.system,
                "messages": request.messages,
                "tools": [t.name for t in request.tools],
                "max_tokens": request.max_tokens,
                "effort": request.effort,
            },
            "turn": turn_to_json(turn),
        }
        out.write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
        return out


class GuardedBackend(Backend):
    """A real provider behind the guard, the ledger and the recorder."""

    def __init__(self, inner: Backend, guard: LiveBudgetGuard, recorder: Recorder | None) -> None:
        self.inner = inner
        self.guard = guard
        self.recorder = recorder
        self.name = f"guarded-{inner.name}"

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.guard.check(request.model, request)
        try:
            turn = self.inner.complete(request)
        except ProviderError:
            # A failed call is recorded at zero cost (providers do not bill failed requests).
            self.guard.charge(self.inner.name, request.model, Usage(), ok=False)
            raise
        self.guard.charge(self.inner.name, request.model, turn.usage, ok=True)
        if self.recorder is not None:
            self.recorder.save(self.guard.phase, self.guard.case, request, turn)
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
    """Serves the recorded turns of one case, in order. No network."""

    name = "replay"

    def __init__(self, folder: Path) -> None:
        self.turns = [
            turn_from_json(json.loads(p.read_text(encoding="utf-8"))["turn"])
            for p in sorted(folder.glob("*.json"))
        ]
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelTurn:
        self.requests.append(request)
        if not self.turns:
            raise ProviderError("the recording has no more turns", fatal=True)
        return self.turns.pop(0)


def replay_gateway(routing: Routing, folder: Path) -> Gateway:
    """A gateway that answers from `folder`'s recording (ReplayLLM)."""
    return Gateway(routing, primary=ReplayBackend(folder), fallback=None, sink=_no_sink)
