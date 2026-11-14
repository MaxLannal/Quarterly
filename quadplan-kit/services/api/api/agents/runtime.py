"""Plumbing shared by the agent harnesses: `llm_call` logging, citation checks, run records
and Server-Sent Events."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, get_args

from llm_gateway.api import CallRecord
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db import models as m
from api.schemas.agents import Citation

logger = logging.getLogger("api.agents")

CITATION_KINDS: tuple[str, ...] = get_args(Citation.model_fields["kind"].annotation)


@dataclass
class RunLog:
    """What one request spent, for `agent_run` and `llm_call` (no user identifier)."""

    records: list[CallRecord] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)

    def sink(self, record: CallRecord) -> None:
        self.records.append(record)

    def step(self, name: str, status: str) -> None:
        self.steps.append({"name": name, "status": status})

    @property
    def tokens(self) -> int:
        return sum(r.in_tokens + r.out_tokens for r in self.records)

    @property
    def cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def model(self) -> str:
        models = [r.model for r in self.records if r.ok]
        return models[-1] if models else "none"

    def save(self, db: Session, run: m.AgentRun) -> None:
        run.steps = list(self.steps)
        run.tokens = self.tokens
        run.cost_usd = Decimal(f"{self.cost:.4f}")
        run.model = self.model[:64]
        today = dt.date.today()
        for r in self.records:
            db.add(
                m.LlmCall(
                    task=r.task[:48],
                    model=r.model[:64],
                    prompt_version=r.prompt_version[:32],
                    in_tokens=r.in_tokens,
                    out_tokens=r.out_tokens,
                    cost_usd=Decimal(f"{r.cost_usd:.6f}"),
                    latency_ms=r.latency_ms,
                    ok=r.ok,
                    created_day=today,
                )
            )
        self.records.clear()


def new_run(db: Session, kind: str, plan_id: Any | None) -> m.AgentRun:
    run = m.AgentRun(
        kind=kind, plan_id=plan_id, model="none", status="running", created_day=dt.date.today()
    )
    db.add(run)
    db.flush()
    return run


def split_ref(ref: str) -> tuple[str, str] | None:
    kind, sep, ident = ref.partition(":")
    if not sep or kind not in CITATION_KINDS or not ident:
        return None
    return kind, ident


def checked_citations(
    task: str, cited: Iterable[tuple[str, str, str]], seen: set[str]
) -> list[Citation]:
    """Keep the citations whose `kind:id` some tool returned in this run; drop and log the
    others (SPEC "Citations are checked")."""
    kept: list[Citation] = []
    dropped = 0
    for kind, ident, label in cited:
        if kind in CITATION_KINDS and f"{kind}:{ident}" in seen:
            if all((c.kind, c.id) != (kind, ident) for c in kept):
                kept.append(Citation.model_validate({"kind": kind, "id": ident, "label": label}))
        else:
            dropped += 1
    if dropped:
        logger.warning("%s: dropped %d citation(s) no tool returned in this run", task, dropped)
    return kept


def sse(event: BaseModel) -> str:
    return f"data: {event.model_dump_json()}\n\n"


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def word_count(text: str) -> int:
    return len(text.split())
