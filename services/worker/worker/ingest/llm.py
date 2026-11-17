"""The model client the ingestion agents use: any `LLM` (the real gateway, or `FakeLLM` in
tests and `--fake` runs) behind a spending cap that also records every `llm_call`.

The cap is checked before every call; once the spend reaches it, calls raise
`CostCapReachedError` (an `LLMUnavailableError`, so every agent takes its fallback path and
the run stops cleanly). Model ids are never named here: `model_for` reports what the
provider said, or the id `llm_routing.yaml` routes the task to.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from llm_gateway.api import AgentResult, AgentSpec, CallRecord, LLMUnavailableError, run_agent
from pydantic import BaseModel


class CostCapReachedError(LLMUnavailableError):
    pass


@dataclass
class Metered:
    inner: Any
    cap_usd: float = float("inf")
    on_record: Callable[[CallRecord], None] | None = None
    spent: float = 0.0
    calls: int = 0
    records: list[CallRecord] = field(default_factory=list)
    _models: dict[str, str] = field(default_factory=dict)

    def _record(self, record: CallRecord) -> None:
        self.spent += record.cost_usd
        self.calls += 1
        self.records.append(record)
        if record.ok:
            self._models[record.task] = record.model
        if self.on_record is not None:
            self.on_record(record)

    def _check(self) -> None:
        if self.spent >= self.cap_usd:
            raise CostCapReachedError(f"spending cap ${self.cap_usd:.2f} reached")

    def structured(self, task: str, **kw: Any) -> Any:
        self._check()
        if hasattr(self.inner, "routing"):  # the real gateway takes a sink
            return self.inner.structured(task, sink=self._record, **kw)
        return self.inner.structured(task, **kw)

    def run_agent[T: BaseModel](self, spec: AgentSpec[T], *, sink: Any = None) -> AgentResult[T]:
        self._check()

        def both(record: CallRecord) -> None:
            self._record(record)
            if sink is not None:
                sink(record)

        return run_agent(self.inner, spec, sink=both)

    def model_for(self, task: str) -> str:
        if task in self._models:
            return self._models[task]
        routing = getattr(self.inner, "routing", None)
        if routing is not None:
            return str(routing.route(task).model)
        return "fake"


def model_of(llm: object, task: str) -> str:
    """The model that served `task` (for `extraction_run.model`)."""
    finder = getattr(llm, "model_for", None)
    return str(finder(task)) if callable(finder) else "fake"
