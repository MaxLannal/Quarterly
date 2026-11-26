"""The planner agent, chat mode (issues #17 and #18): the advisor chat of prompt 07, folded into
the planner agent and following data/planner/plan-guideline.md.

1. **Typed confirmation** (deterministic, no model): "apply it" or "I agree to add ... to
   ...". It is accepted when the parsed operations equal the latest proposal's (or "apply it"
   names the latest proposal) or are fully explicit, and the plan still has the proposal's
   hash. The answer is a `confirm` event; the student's own browser applies it (a saved plan
   through POST /plans/{id}/changesets/{cs}/apply, which parses the text again).
2. **Scope gate** (Haiku): `off_topic` and `suspicious` get a fixed one-line refusal without
   calling the main model; `confirmation` that the parser could not read gets the help line.
3. **Planner** (Opus 5.5, `a1_planner_chat`): read tools, `preview_ops`, the draft tool
   `propose_change_set` (one course or sequence each, at most `chat_proposals_max`) and
   `note_preference`, which adds one dated line to the working information. No tool applies a
   change. The answer is `{text, citations}`; citations no tool returned are dropped.

History is kept per saved plan (`agent_run` kind `chat` + `chat_message`) as long as the plan
exists (issue #17 D1); Clear chat deletes it. A plan that lives only in the browser keeps its
history in the browser.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, cast

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
from llm_gateway.types import Tool, ToolOutput
from planner_core import verify_checked
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.hashing import plan_hash
from planner_core.models import AddOp, ChangeOp, ChangeSet, Report
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.agents.confirm import HELP, fully_explicit, ops_equal, parse_confirmation
from api.agents.planner.guideline import PlannerConfig, Rule, load_guideline, load_planner_config
from api.agents.planner.standards import PREFERENCE_KINDS, avoided_courses, preference_line
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog, checked_citations, citable_ids
from api.agents.tools import _OPS_SCHEMA, A2_TOOLS, OpsIn, ToolBox, _obj, to_json
from api.db import models as m
from api.forum.scrub import scrub
from api.profile_data import ensure_profile, profile_out, render_student_md
from api.repo import plans as plans_repo
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.schemas.agents import (
    ChatEntry,
    ChatHistory,
    Citation,
    ConfirmEvent,
    DoneEvent,
    ErrorEvent,
    MessageEvent,
)
from api.schemas.planner import PlannerProposalEvent, PlannerRequest, RuleRef, Verdict

logger = logging.getLogger("api.agents")

TASK = "a1_planner_chat"
TASK_SCOPE = "a2_scope_classifier"
CHAT_BUDGET = Budget(tool_calls=10, tokens=160_000, seconds=90)
SCOPE_TIMEOUT_S = 8.0
HISTORY_TURNS = 10
MAX_ANSWER_CHARS = 1200
#: Usage rows (agent_run) of browser-plan chats are kept this long, like before.
USAGE_DAYS = 30
#: The tools of the planner chat: the advisor's read and draft tools plus note_preference.
CHAT_TOOLS = (*A2_TOOLS, "note_preference")

OFF_TOPIC = "I can only help with planning your courses."
SUSPICIOUS = "I can't help with that. I can answer questions about your courses and your plan."
UNAVAILABLE = "The planner can't answer right now. You can still edit your plan by hand."
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
                        "enum": [
                            "course", "attribute", "post", "summary", "program", "profile",
                            "guideline",
                        ],
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
}  # fmt: skip

_PROPOSE_SCHEMA = _obj(
    {
        "ops": _OPS_SCHEMA["properties"]["ops"],
        "title": {"type": "string", "description": 'Short, e.g. "A new Humanities sequence"'},
        "kind": {"type": "string", "enum": ["major", "core", "elective", "minor", "other"]},
        "why": {"type": "string", "description": "Two or three sentences for this student."},
        "rules": {"type": "array", "items": {"type": "string"}, "description": "e.g. G23"},
    }
)
_NOTE_SCHEMA = _obj(
    {
        "text": {"type": "string", "description": "The preference in the student's words."},
        "kind": {"type": "string", "enum": list(PREFERENCE_KINDS)},
        "courses": {"type": "array", "items": {"type": "string"}, "description": "Codes"},
    }
)


# --------------------------------------------------------------------- history


def purge_old_history(db: Session) -> int:
    """The planner chat is kept while its plan exists (issue #17 D1). Messages of a chat whose
    plan is gone are deleted; usage rows of browser-plan chats go after 30 days."""
    orphans = sa.select(m.AgentRun.id).where(
        m.AgentRun.kind == "chat", m.AgentRun.plan_id.is_(None)
    )
    gone = db.execute(sa.delete(m.ChatMessage).where(m.ChatMessage.run_id.in_(orphans)))
    # A paused planner run holds the answers given so far (a logged-out student's too): it goes
    # after `state_ttl_days`, also when nobody resumes it (final review).
    ttl = dt.date.today() - dt.timedelta(days=load_planner_config().state_ttl_days)
    db.execute(
        sa.update(m.AgentRun)
        .where(
            m.AgentRun.kind == "planner",
            m.AgentRun.state.is_not(None),
            m.AgentRun.created_day < ttl,
        )
        .values(state=None)
    )
    cutoff = dt.date.today() - dt.timedelta(days=USAGE_DAYS)
    db.execute(
        sa.delete(m.AgentRun).where(
            m.AgentRun.kind == "chat",
            m.AgentRun.plan_id.is_(None),
            m.AgentRun.created_day < cutoff,
        )
    )
    return int(getattr(gone, "rowcount", 0) or 0)


def forget_chats(db: Session, plan_ids: list[uuid.UUID]) -> None:
    """A plan's chats go with the plan (plan or account deletion); the messages follow by
    cascade."""
    if plan_ids:
        db.execute(
            sa.delete(m.AgentRun).where(m.AgentRun.kind == "chat", m.AgentRun.plan_id.in_(plan_ids))
        )


def clear_history(db: Session, plan: m.Plan) -> int:
    """Clear chat (issue #18): the plan's messages go; its proposals stay on the grid."""
    runs = sa.select(m.AgentRun.id).where(m.AgentRun.kind == "chat", m.AgentRun.plan_id == plan.id)
    gone = db.execute(sa.delete(m.ChatMessage).where(m.ChatMessage.run_id.in_(runs)))
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
            .where(m.AgentRun.plan_id == plan.id, m.AgentRun.kind == "chat")
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
                    ChatEntry(
                        role="proposal", change_set=plans_repo.change_set_model(cs), meta=cs.meta
                    )
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


# --------------------------------------------------------------------- tools


@dataclass
class Drafted:
    ops: list[ChangeOp]
    report: Report
    base_plan_hash: str
    title: str
    kind: str
    why: str
    rules: list[str]


@dataclass
class ChatTools:
    """The planner's own tools on top of the advisor's ToolBox."""

    box: ToolBox
    config: PlannerConfig
    avoid: set[str]
    today: dt.date
    drafted: list[Drafted] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def propose(self, args: dict[str, Any]) -> ToolOutput:
        if len(self.drafted) >= self.config.chat_proposals_max:
            raise ValueError("You already proposed the most changes allowed in one answer.")
        ops = [o.to_op() for o in OpsIn.model_validate({"ops": args.get("ops")}).ops]
        avoided = [o.course for o in ops if isinstance(o, AddOp) and o.course in self.avoid]
        if avoided:
            raise ValueError(
                f"The student said they do not want {', '.join(c for c in avoided if c)} "
                "(G16). Propose something else."
            )
        _, report = self.box._preview({"ops": args.get("ops")})
        self.drafted.append(
            Drafted(
                ops=ops,
                report=report,
                base_plan_hash=plan_hash(self.box.state),
                title=str(args.get("title") or "A change to your plan")[:80],
                kind=str(args.get("kind") or "other"),
                why=str(args.get("why") or "")[:800],
                rules=[str(r) for r in args.get("rules") or []][:8],
            )
        )
        verdict = self.box._verdict(report)
        verdict["proposal"] = f"p{len(self.drafted)}"
        verdict["note"] = (
            "The student sees this as an unsaved block on the plan. Nothing is applied until "
            "they accept it or type a confirmation."
        )
        return ToolOutput(to_json(verdict))

    def note(self, args: dict[str, Any]) -> ToolOutput:
        kind = args.get("kind") if args.get("kind") in PREFERENCE_KINDS else "other"
        courses = [str(c) for c in args.get("courses") or []]
        line = preference_line(self.today, str(kind), str(args.get("text") or ""), courses)
        self.notes.append(line)
        if kind == "avoid":
            self.avoid |= set(avoided_courses(line))
        return ToolOutput(to_json({"noted": line}))

    def tools(self) -> list[Tool]:
        own = {
            "propose_change_set": Tool(
                "propose_change_set",
                "Show the student ONE proposal for one course or sequence (an unsaved block on "
                "the plan, with the verifier's verdict). At most three per answer.",
                _PROPOSE_SCHEMA,
                self.propose,
            ),
            "note_preference": Tool(
                "note_preference",
                "Record a preference that should last in the working information (one dated "
                "line). kind avoid: the courses are never proposed again.",
                _NOTE_SCHEMA,
                self.note,
            ),
        }
        out: list[Tool] = []
        for name in CHAT_TOOLS:
            out += [own[name]] if name in own else self.box.tools([name])
        return out


# --------------------------------------------------------------------- the harness


@dataclass
class PlannerChat:
    db: Session
    llm: object
    req: PlannerRequest
    show_unpublished: bool
    statuses: tuple[str, ...]
    log: RunLog
    #: The saved plan this conversation belongs to (history and proposals on the server).
    saved: m.Plan | None = None
    account: m.Account | None = None
    config: PlannerConfig = field(default_factory=load_planner_config)
    today: dt.date = field(default_factory=dt.date.today)
    #: New working-information lines of this turn.
    new_notes: list[str] = field(default_factory=list)

    @property
    def logged_in(self) -> bool:
        return self.account is not None

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
                created_day=self.today,
            )
        )

    def _working_notes(self) -> str:
        if self.account is not None:
            return (ensure_profile(self.db, self.account.id).working_notes or "").strip()
        return (self.req.working_notes or "").strip()

    def _store_notes(self) -> str | None:
        """Append the turn's preferences: to the record (logged in), or back to the browser."""
        if not self.new_notes:
            return None
        if self.account is not None:
            row = ensure_profile(self.db, self.account.id)
            old = (row.working_notes or "").strip()
            row.working_notes = "\n".join(x for x in (old, *self.new_notes) if x)
            return None
        old = (self.req.working_notes or "").strip()
        return "\n".join(x for x in (old, *self.new_notes) if x)

    def _finish(self) -> DoneEvent:
        notes = self._store_notes()
        if self.saved is not None:
            run = chat_run(self.db, self.saved)
            self.log.save(self.db, run)
            run_id = str(run.id)
        else:
            if self.log.records:
                run = m.AgentRun(kind="chat", plan_id=None, model="none", status="ok")
                run.created_day = self.today
                self.db.add(run)
                self.db.flush()
                self.log.save(self.db, run)
            run_id = str(self.req.run_id or uuid.uuid4())
        self.db.commit()
        return DoneEvent(run_id=run_id, working_notes=notes)

    def _reply(self, text: str, citations: list[Citation] | None = None) -> MessageEvent:
        self._say("assistant", text, citations)
        return MessageEvent(text=text, citations=citations or [])

    def events(self) -> Iterator[BaseModel]:
        message = scrub((self.req.message or "").strip())  # no emails or phone numbers kept
        if not message:
            yield ErrorEvent(message="Type a message first.")
            return
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
            yield from self._advise(message)
        yield self._finish()

    # ---------------------------------------------------------------- confirmations

    def _latest(self) -> ChangeSet | None:
        if self.saved is not None:
            row = latest_proposal_row(self.db, self.saved)
            if row is None or row.status != "proposed":
                return None
            return plans_repo.change_set_model(row)
        if not self.req.pending:
            return None
        p = self.req.pending[-1]
        return ChangeSet(origin="chat", ops=p.ops, base_plan_hash=p.base_plan_hash)

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
            # The planner's own prompt keeps it on topic; a failed gate is not a refusal.
            logger.info("%s: scope gate unavailable (%s)", TASK_SCOPE, type(exc).__name__)
            return Scope(label="in_scope")

    # ---------------------------------------------------------------- planner

    def _history(self) -> list[Message]:
        if self.saved is not None:
            rows = [r for r in _messages(self.db, self.saved) if r.role in ("user", "assistant")]
            turns = [Message(r.role, r.content) for r in rows][:-1]  # without this message
        else:
            # Sent by the browser as typed: scrub it like the new message.
            turns = [Message(t.role, scrub(t.text)) for t in self.req.history]
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

    def _record(self) -> dict[str, Any]:
        if self.account is not None:
            row = ensure_profile(self.db, self.account.id)
            return profile_out(self.db, self.account, row).model_dump(mode="json")
        return dict(self.req.profile_answers)

    def _context(self, record: dict[str, Any]) -> str:
        if self.account is not None:
            md = render_student_md(self.db, ensure_profile(self.db, self.account.id), grades=False)
        else:
            row = m.StudentProfile(research_areas=[], interests=[], intended_programs=[])
            for f in ("interests", "research_areas", "intended_programs"):
                if isinstance(record.get(f), list):
                    setattr(row, f, [str(x) for x in record[f]])
            for f in ("post_grad_plan", "pace", "course_load", "theory_vs_application"):
                if record.get(f) is not None:
                    setattr(row, f, record[f])
            with self.db.no_autoflush:
                md = render_student_md(self.db, row, grades=False)
        notes = self._working_notes() or "None yet."
        return f"# The student's record (student.md)\n\n{md}\n\n# Working information\n\n{notes}\n"

    def _advise(self, message: str) -> Iterator[BaseModel]:
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
        record = self._record()
        tools = ChatTools(
            box=box,
            config=self.config,
            avoid=set(avoided_courses(self._working_notes())),
            today=self.today,
        )
        prompt = load_prompt("a1_planner_chat")
        guideline = load_guideline()
        fields = {f for f, v in record.items() if v not in (None, "", [], {})}
        latest = Message("user", f"{self._context(record)}\n# Message\n\n{message}")
        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=f"{prompt.text}\n\n# Plan guideline\n\n{guideline.text}",
            messages=[*self._history(), latest],
            tools=tools.tools(),
            submit=SubmitTool(
                "submit_answer",
                "Your reply to the student, with citations.",
                Answer,
                input_schema=_ANSWER_SCHEMA,
                strict=True,
            ),
            budget=CHAT_BUDGET,
            known_ids=citable_ids(profile_fields=fields, guideline_ids=guideline.rules),
        )
        try:
            result = run_agent(self.llm, spec, sink=self.log.sink)
        except AgentError as exc:
            logger.info("%s: no answer (%s)", TASK, exc.reason)
            yield ErrorEvent(message=UNAVAILABLE, reason="unavailable")
            return
        self.new_notes = list(tools.notes)
        citations = checked_citations(
            TASK, ((c.kind, c.id, c.label) for c in result.output.citations), result.seen_ids
        )
        yield self._reply(result.output.text.strip(), citations)
        yield from self._proposals(tools, guideline.rules)

    def _proposals(self, tools: ChatTools, rules: dict[str, Rule]) -> Iterator[BaseModel]:
        for n, d in enumerate(tools.drafted, 1):
            refs = [RuleRef(id=r, text=rules[r].text) for r in d.rules if r in rules]
            kind = d.kind if d.kind in ("major", "core", "elective", "minor") else "other"
            group_id = f"chat-{uuid.uuid4().hex[:8]}-{n}"
            change_set_id = None
            if self.saved is not None:
                row = plans_repo.store_change_set(
                    self.db,
                    self.saved,
                    origin="chat",
                    ops=d.ops,
                    base_plan_hash=d.base_plan_hash,
                    preview=d.report,
                )
                row.run_id = chat_run(self.db, self.saved).id
                row.meta = {
                    "group_id": group_id,
                    "title": d.title,
                    "kind": kind,
                    "why": d.why,
                    "citations": [],
                    "rules": [r.model_dump() for r in refs],
                }
                self.db.flush()
                self._say("proposal", str(row.id))
                change_set_id = str(row.id)
            yield PlannerProposalEvent.model_validate(
                {
                    "change_set_id": change_set_id,
                    "group_id": group_id,
                    "title": d.title,
                    "kind": kind,
                    "ops": d.ops,
                    "why": d.why,
                    "citations": [],
                    "rules": refs,
                    "preview": Verdict.model_validate(tools.box._verdict(d.report)),
                    "base_plan_hash": d.base_plan_hash,
                }
            )


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
            return '"Apply it" confirms only the latest proposal in the planner chat.'
        return None
    if not ops_equal(parsed.ops, list(plans_repo.change_set_model(row).ops)):
        return "The typed change does not match this proposal."
    return None
