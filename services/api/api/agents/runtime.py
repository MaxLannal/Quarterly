"""Plumbing shared by the agent harnesses: `llm_call` logging, citation checks, run records
and Server-Sent Events."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from typing import Any, get_args
from urllib.parse import quote

import sqlalchemy as sa
from llm_gateway.api import CallRecord
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.campus_tools import guide_entry
from api.agents.live import known_courses, normalize_code
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


def citation_label(kind: str, ident: str) -> str:
    """The chip text, built by the server from the id: the model's own label is ignored, so
    text from a forum post cannot reach the chip through the model."""
    if kind == "attribute":
        code, _, key = ident.rpartition(":")
        return f"{code}: {key.replace('_', ' ')}"
    if kind == "post":
        return f"Student post #{ident}"
    if kind == "summary":
        return "What students say"
    if kind == "profile":
        label = _field_labels().get(ident)
        return f"Your {label[0].lower()}{label[1:]}" if label else "Your record"
    if kind == "guideline":
        return f"Guideline {ident}"
    return ident  # a course code or a program id


@lru_cache(maxsize=1)
def _field_labels() -> dict[str, str]:
    from api.profile_questions import question_set

    return {q.field: q.label for q in question_set().questions}


def citable_ids(*, profile_fields: Iterable[str], guideline_ids: Iterable[str]) -> set[str]:
    """The `profile:` and `guideline:` ids a planner answer may cite: the student's answered
    General Information fields and the rules that exist. Add them to the run's known ids."""
    return {f"profile:{f}" for f in profile_fields} | {f"guideline:{g}" for g in guideline_ids}


def checked_citations(
    task: str, cited: Iterable[tuple[str, str, str]], seen: set[str]
) -> list[Citation]:
    """Keep the citations whose `kind:id` some tool returned in this run; drop and log the
    others (SPEC "Citations are checked"). Labels are rebuilt by `citation_label`."""
    kept: list[Citation] = []
    dropped = 0
    for kind, ident, _model_label in cited:
        if kind in CITATION_KINDS and f"{kind}:{ident}" in seen:
            if all((c.kind, c.id) != (kind, ident) for c in kept):
                label = citation_label(kind, ident)
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


# --------------------------------------------------------------------- source chips

#: The kinds of source a campus agent can cite (the Commons bot's `CommonsCitation.kind`).
SOURCE_KINDS: tuple[str, ...] = (
    "course",
    "program",
    "post",
    "summary",
    "attribute",
    "thread",
    "guide",
)
MAX_SOURCES = 12


@dataclass(frozen=True)
class CitedSource:
    """A source chip. `label` and `href` are built here from the id (never by the model):
    `href` is a path on this site, or an https page on uchicago.edu for `guide`."""

    kind: str
    id: str
    label: str
    href: str


def course_href(code: str) -> str:
    return f"/courses/{quote(code, safe='')}"


def page_href(code: str, slug: str) -> str:
    return f"{course_href(code)}/i/{quote(slug, safe='')}"


def clip(text: str, limit: int) -> str:
    """`text` on one line, at most `limit` characters (an ellipsis marks a cut)."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass
class Citer:
    """Checks citations against the ids the run saw and builds their chips from the database.
    Used by the Commons bot (moved here from the removed Ask chatbot, issue #15)."""

    db: Session
    seen: set[str]
    kept: list[CitedSource] = field(default_factory=list)
    dropped: int = 0

    def add(self, kind: str, ident: str) -> None:
        ident = ident.strip()
        if kind == "course":
            ident = normalize_code(ident) or ident
        if kind not in SOURCE_KINDS or f"{kind}:{ident}" not in self.seen:
            self.dropped += 1
            return
        if any((c.kind, c.id) == (kind, ident) for c in self.kept):
            return
        chip = self._chip(kind, ident)
        if chip is None:
            self.dropped += 1
        elif len(self.kept) < MAX_SOURCES:
            self.kept.append(chip)

    def _chip(self, kind: str, ident: str) -> CitedSource | None:
        label: str | None = None
        href: str | None = None
        if kind == "course":
            title = known_courses(self.db, [ident]).get(ident)
            if title is not None:
                label, href = f"{ident} · {title}", course_href(ident)
        elif kind == "attribute":
            code, _, key = ident.rpartition(":")
            if code:
                label, href = f"{code}: {key.replace('_', ' ')}", course_href(code)
        elif kind == "program":
            name = self.db.scalar(sa.select(m.Program.name).where(m.Program.id == ident))
            if name is not None:
                label, href = name, f"/programs/{quote(ident, safe='')}"
        elif kind == "thread" and ident.isdigit():
            title = self.db.scalar(
                sa.select(m.CommonsThread.title).where(
                    m.CommonsThread.id == int(ident), m.CommonsThread.status == "visible"
                )
            )
            if title is not None:
                label, href = f"Forum: {clip(title, 60)}", f"/forum/t/{ident}"
        elif kind == "guide":
            entry = guide_entry(ident)
            if entry is not None:
                label, href = entry.title, entry.source_url
        elif kind in ("post", "summary") and ident.isdigit():
            found = self._forum_page(kind, int(ident))
            if found is not None:
                code, slug = found
                if kind == "post":
                    label, href = f"Student post on {code}", f"{page_href(code, slug)}/t/{ident}"
                else:
                    label, href = f"What students say about {code}", page_href(code, slug)
        if label is None or href is None:
            return None
        return CitedSource(kind=kind, id=ident, label=clip(label, 90), href=href)

    def _forum_page(self, kind: str, ident: int) -> tuple[str, str] | None:
        stmt = (
            sa.select(m.Course.code, m.Instructor.slug)
            .select_from(m.CourseInstructor)
            .join(m.Course, m.Course.id == m.CourseInstructor.course_id)
            .join(m.Instructor, m.Instructor.id == m.CourseInstructor.instructor_id)
        )
        if kind == "post":
            stmt = stmt.join(m.Post, m.Post.course_instructor_id == m.CourseInstructor.id).where(
                m.Post.id == ident, m.Post.status == "visible"
            )
        else:
            stmt = stmt.where(m.CourseInstructor.id == ident)
        row = self.db.execute(stmt.limit(1)).first()
        return (row[0], row[1]) if row else None
