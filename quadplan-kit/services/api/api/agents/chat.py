"""A2 advisor chat harness (SPEC "A2. Advisor chat").

1. **Typed confirmation** (deterministic, no model): "apply it" or "I agree to add ... to
   ...". It is accepted when the parsed operations equal the latest proposal's (or "apply it"
   names the latest proposal) or are fully explicit, and the plan still has the proposal's
   hash. The answer is a `confirm` event; the student's own browser applies it (a saved plan
   through POST /plans/{id}/changesets/{cs}/apply, which parses the text again).
2. **Scope gate** (Haiku): `off_topic` and `suspicious` get a fixed one-line refusal without
   calling the main model; `confirmation` that the parser could not read gets the help line.
3. **Advisor** (Sonnet, Opus to compare whole plans): read tools, `preview_ops` and one draft
   tool, `propose_change_set`. No tool applies anything. The answer is `{text, citations}`;
   citations whose id no tool returned in this run are dropped.

History is kept per saved plan (`agent_run` kind `chat` + `chat_message`) and deleted after
30 days. A plan that lives only in the browser keeps its history in the browser.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, cast

import sqlalchemy as sa
from llm_gateway.api import (
    LLM,
    AgentError,
    AgentSpec,
    Budget,
    LLMUnavailableError,
    Message,
    SubmitTool,
    run_agent,
)
from planner_core import verify_checked
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.hashing import plan_hash
from planner_core.models import ChangeOp, ChangeSet
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.agents.confirm import HELP, fully_explicit, ops_equal, parse_confirmation
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog, checked_citations
from api.agents.tools import A2_TOOLS, ToolBox
from api.db import models as m
from api.forum.scrub import scrub
from api.repo import plans as plans_repo
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.schemas.agents import (
    ChatEntry,
    ChatHistory,
    ChatRequest,
    Citation,
    ConfirmEvent,
    DoneEvent,
    ErrorEvent,
    MessageEvent,
    ProposalEvent,
)

logger = logging.getLogger("api.agents")

TASK = "a2_advisor_chat"
TASK_ESCALATION = "a2_advisor_chat_escalation"
TASK_SCOPE = "a2_scope_classifier"
CHAT_BUDGET = Budget(tool_calls=10, tokens=120_000, seconds=45)
ESCALATION_BUDGET = Budget(tool_calls=12, tokens=200_000, seconds=75)
SCOPE_TIMEOUT_S = 8.0
HISTORY_DAYS = 30
HISTORY_TURNS = 10
MAX_ANSWER_CHARS = 1200

OFF_TOPIC = "I can only help with planning your courses."
SUSPICIOUS = "I can't help with that. I can answer questions about your courses and your plan."
UNAVAILABLE = "The advisor can't answer right now. You can still edit your plan by hand."
STALE = (
    "Your plan changed since that proposal, so I did not apply it. Ask again and I will "
    "make a new proposal."
)
NO_PROPOSAL = "There is no proposal to apply yet. " + HELP


class Scope(BaseModel):
    label: Literal["in_scope", "off_topic", "confirmation", "suspicious"]
    escalate: bool = False


class CitationIn(BaseModel):
    kind: str
    id: str
    label: str = Field(max_length=120)


class Answer(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    citations: list[CitationIn] = Field(default=[], max_length=12)


_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "Your reply, under 120 words."},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["course", "attribute", "post", "summary", "program"],
                    },
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["kind", "id", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["text", "citations"],
    "additionalProperties": False,
}


# --------------------------------------------------------------------- history


def _cutoff() -> dt.date:
    return dt.date.today() - dt.timedelta(days=HISTORY_DAYS)


def purge_old_history(db: Session) -> int:
    """Delete chat messages older than 30 days, and chat runs left empty (SPEC table
    `chat_message`: deleted after 30 days)."""
    gone = db.execute(sa.delete(m.ChatMessage).where(m.ChatMessage.created_day < _cutoff()))
    db.execute(
        sa.delete(m.AgentRun).where(
            m.AgentRun.kind == "chat",
            m.AgentRun.created_day < _cutoff(),
            ~sa.exists().where(m.ChatMessage.run_id == m.AgentRun.id),
        )
    )
    return int(getattr(gone, "rowcount", 0) or 0)


def chat_run(db: Session, plan: m.Plan) -> m.AgentRun:
    """The plan's conversation (one `agent_run` of kind `chat` per plan)."""
    run = db.scalar(
        sa.select(m.AgentRun)
        .where(m.AgentRun.kind == "chat", m.AgentRun.plan_id == plan.id)
        .order_by(m.AgentRun.created_day.desc())
        .limit(1)
    )
    if run is None:
        run = m.AgentRun(
            kind="chat", plan_id=plan.id, model="none", status="ok", created_day=dt.date.today()
        )
        db.add(run)
        db.flush()
    return run


def _messages(db: Session, plan: m.Plan) -> list[m.ChatMessage]:
    return list(
        db.scalars(
            sa.select(m.ChatMessage)
            .join(m.AgentRun, m.AgentRun.id == m.ChatMessage.run_id)
            .where(
                m.AgentRun.plan_id == plan.id,
                m.AgentRun.kind == "chat",
                m.ChatMessage.created_day >= _cutoff(),
            )
            .order_by(m.ChatMessage.id)
        )
    )


def latest_proposal_row(db: Session, plan: m.Plan) -> m.ChangeSet | None:
    """The change set of the newest proposal card in the plan's chat (a `proposal` message
    holds the change set id)."""
    msg = db.scalar(
        sa.select(m.ChatMessage)
        .join(m.AgentRun, m.AgentRun.id == m.ChatMessage.run_id)
        .where(
            m.AgentRun.plan_id == plan.id,
            m.AgentRun.kind == "chat",
            m.ChatMessage.role == "proposal",
            m.ChatMessage.created_day >= _cutoff(),
        )
        .order_by(m.ChatMessage.id.desc())
        .limit(1)
    )
    if msg is None:
        return None
    try:
        return db.get(m.ChangeSet, uuid.UUID(msg.content))
    except ValueError:
        return None


def history(db: Session, plan: m.Plan) -> ChatHistory:
    rows = _messages(db, plan)
    entries: list[ChatEntry] = []
    for row in rows:
        if row.role == "proposal":
            try:
                cs = db.get(m.ChangeSet, uuid.UUID(row.content))
            except ValueError:
                cs = None
            if cs is not None:
                entries.append(
                    ChatEntry(role="proposal", change_set=plans_repo.change_set_model(cs))
                )
        elif row.role in ("user", "assistant"):
            entries.append(
                ChatEntry.model_validate(
                    {
                        "role": row.role,
                        "text": row.content,
                        "citations": [Citation.model_validate(c) for c in row.citations],
                    }
                )
            )
    return ChatHistory(run_id=str(rows[-1].run_id) if rows else None, entries=entries)


# --------------------------------------------------------------------- the harness


@dataclass
class ChatRun:
    db: Session
    llm: object
    req: ChatRequest
    show_unpublished: bool
    statuses: tuple[str, ...]
    log: RunLog
    #: The saved plan this conversation belongs to (history and proposals on the server).
    saved: m.Plan | None = None
    #: Logged-out runs get no forum tools (posts and summaries need login).
    logged_in: bool = False

    def _say(self, role: str, content: str, citations: list[Citation] | None = None) -> None:
        if self.saved is None:
            return
        run = chat_run(self.db, self.saved)
        self.db.add(
            m.ChatMessage(
                run_id=run.id,
                role=role,
                content=content,
                citations=[c.model_dump() for c in citations or []],
                created_day=dt.date.today(),
            )
        )

    def _finish(self) -> DoneEvent:
        if self.saved is not None:
            run = chat_run(self.db, self.saved)
            self.log.save(self.db, run)
            run_id = str(run.id)
        else:
            if self.log.records:
                run = m.AgentRun(kind="chat", plan_id=None, model="none", status="ok")
                run.created_day = dt.date.today()
                self.db.add(run)
                self.db.flush()
                self.log.save(self.db, run)
            run_id = self.req.run_id or str(uuid.uuid4())
        self.db.commit()
        return DoneEvent(run_id=run_id)

    def _reply(self, text: str, citations: list[Citation] | None = None) -> MessageEvent:
        self._say("assistant", text, citations)
        return MessageEvent(text=text, citations=citations or [])

    def events(self) -> Iterator[BaseModel]:
        message = scrub(self.req.message.strip())  # no emails or phone numbers kept or sent
        self._say("user", message)
        confirmation = parse_confirmation(message, self.req.plan.entry_term)
        if confirmation is not None:
            yield from self._confirm(confirmation.affirm, confirmation.ops, message)
            yield self._finish()
            return

        scope = self._scope(message)
        if scope.label == "off_topic":
            yield self._reply(OFF_TOPIC)
        elif scope.label == "suspicious":
            yield self._reply(SUSPICIOUS)
        elif scope.label == "confirmation":
            yield self._reply(HELP)
        else:
            yield from self._advise(message, escalate=scope.escalate)
        yield self._finish()

    # ---------------------------------------------------------------- confirmations

    def _latest(self) -> ChangeSet | None:
        if self.saved is not None:
            row = latest_proposal_row(self.db, self.saved)
            if row is None or row.status != "proposed":
                return None
            return plans_repo.change_set_model(row)
        latest = self.req.latest_proposal
        return latest if latest is not None and latest.status == "proposed" else None

    def _confirm(self, affirm: bool, typed: list[ChangeOp], text: str) -> Iterator[BaseModel]:
        state = self.req.plan
        current = plan_hash(state)
        latest = self._latest()
        target: ChangeSet | None = None
        if latest is not None and (affirm or ops_equal(typed, list(latest.ops))):
            if latest.base_plan_hash != current:
                yield self._reply(STALE)
                return
            target = latest
        elif affirm:
            yield self._reply(NO_PROPOSAL)
            return
        elif fully_explicit(typed):
            try:
                after = apply_ops(state, typed)
                rules, catalog = load_verify_inputs(
                    self.db, after, show_unpublished=self.show_unpublished
                )
            except (ChangeOpError, UnknownProgramsError) as exc:
                yield self._reply(f"That change does not fit your plan: {exc}")
                return
            report, _ = verify_checked(after, rules, catalog)
            target = ChangeSet(
                origin="user", ops=typed, base_plan_hash=current, preview_report=report
            )
            if self.saved is not None:
                row = plans_repo.store_change_set(
                    self.db,
                    self.saved,
                    origin="user",
                    ops=typed,
                    base_plan_hash=current,
                    preview=report,
                )
                target = plans_repo.change_set_model(row)
        else:
            yield self._reply(
                "That does not match the latest proposal, and it leaves out a quarter, so I "
                "did not apply it. " + HELP
            )
            return
        yield ConfirmEvent(change_set=target, confirmation_text=text)

    # ---------------------------------------------------------------- scope gate

    def _scope(self, message: str) -> Scope:
        prompt = load_prompt("a2_scope")
        try:
            out = cast(LLM, self.llm).structured(
                TASK_SCOPE,
                system=prompt.text,
                messages=[Message("user", message)],
                schema=Scope,
                prompt_version=prompt.version_tag,
                timeout_s=SCOPE_TIMEOUT_S,
            )
            return out if isinstance(out, Scope) else Scope.model_validate(out)
        except (LLMUnavailableError, TimeoutError) as exc:
            # The advisor's own prompt keeps it on topic; a failed gate is not a refusal.
            logger.info("%s: scope gate unavailable (%s)", TASK_SCOPE, type(exc).__name__)
            return Scope(label="in_scope")

    # ---------------------------------------------------------------- advisor

    def _history(self) -> list[Message]:
        if self.saved is not None:
            rows = [r for r in _messages(self.db, self.saved) if r.role in ("user", "assistant")]
            turns = [Message(r.role, r.content) for r in rows][:-1]  # without this message
        else:
            turns = [Message(t.role, t.text) for t in self.req.history]
        turns = turns[-HISTORY_TURNS:]
        while turns and turns[0].role != "user":
            turns = turns[1:]
        merged: list[Message] = []
        for t in turns:  # the API needs alternating roles
            if merged and merged[-1].role == t.role:
                merged[-1] = Message(t.role, merged[-1].content + "\n\n" + t.content)
            else:
                merged.append(t)
        if merged and merged[-1].role == "user":
            merged.append(Message("assistant", "(no answer)"))
        return merged

    def _advise(self, message: str, *, escalate: bool) -> Iterator[BaseModel]:
        state = self.req.plan
        try:
            rules, catalog = load_verify_inputs(
                self.db, state, show_unpublished=self.show_unpublished
            )
        except UnknownProgramsError:
            yield ErrorEvent(message="Your plan lists a program that is not in the catalog.")
            return
        report, _ = verify_checked(state, rules, catalog)
        box = ToolBox(
            db=self.db,
            state=state,
            report=report,
            statuses=self.statuses,
            show_unpublished=self.show_unpublished,
            logged_in=self.logged_in,
        )
        prompt = load_prompt("a2_chat")
        spec = AgentSpec(
            task=TASK_ESCALATION if escalate else TASK,
            prompt_version=prompt.version_tag,
            system=prompt.text,
            messages=[*self._history(), Message("user", message)],
            tools=box.tools(A2_TOOLS),
            submit=SubmitTool(
                "submit_answer",
                "Your reply to the student, with citations.",
                Answer,
                input_schema=_ANSWER_SCHEMA,
                strict=True,
            ),
            budget=ESCALATION_BUDGET if escalate else CHAT_BUDGET,
        )
        try:
            result = run_agent(self.llm, spec, sink=self.log.sink)
        except AgentError as exc:
            logger.info("%s: no answer (%s)", TASK, exc.reason)
            yield ErrorEvent(message=UNAVAILABLE)
            return
        citations = checked_citations(
            TASK,
            ((c.kind, c.id, c.label) for c in result.output.citations),
            result.seen_ids,
        )
        yield self._reply(result.output.text.strip(), citations)
        for cs in box.change_sets():
            if self.saved is not None:
                row = plans_repo.store_change_set(
                    self.db,
                    self.saved,
                    origin="chat",
                    ops=list(cs.ops),
                    base_plan_hash=cs.base_plan_hash,
                    preview=cs.preview_report,
                )
                self._say("proposal", str(row.id))
                cs = plans_repo.change_set_model(row)
            yield ProposalEvent(change_set=cs)


def confirmation_problem(
    db: Session, plan: m.Plan, row: m.ChangeSet, text: str, terms: list[str] | None
) -> str | None:
    """Why `text` does not confirm change set `row` of `plan` (None when it does). Used by
    POST /plans/{id}/changesets/{cs}/apply with `confirmation_text`; the plan-hash check
    follows there."""
    if terms is not None:
        return "A typed confirmation applies the whole proposal; leave out the quarters."
    parsed = parse_confirmation(text, plan.entry_term)
    if parsed is None:
        return "That is not a confirmation. " + HELP
    if parsed.affirm:
        latest = latest_proposal_row(db, plan)
        if latest is None or latest.id != row.id:
            return '"Apply it" confirms only the latest proposal in the advisor chat.'
        return None
    if not ops_equal(parsed.ops, list(plans_repo.change_set_model(row).ops)):
        return "The typed change does not match this proposal."
    return None
