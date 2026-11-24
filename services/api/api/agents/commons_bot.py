"""A9 Commons bot: the AI's answer under a Commons question (docs/BEST-OF-UCHICAGO-PLAN.md).

POST /commons/threads/{id}/bot streams one run:

- A stored answer (and no `regenerate` / `reply_to`) is sent back at once as one `answer`.
- Otherwise the agent (task `a9_commons_bot`) reads the catalog, programs, the forum's reviews
  (logged-in readers only), other Commons questions and the campus guide through the shared
  campus tools (`api.agents.campus_tools`); each tool call is streamed as a `step` while the
  model works (`run_live`). The model ends with `submit_answer` {text, citations}; citations
  whose id no tool returned in this run are dropped and every chip is rebuilt from the id.
- The harness, not the agent, stores the answer: a `commons_reply` of kind `bot` with no author
  (top-level, or nested under the reply that summoned it with @quarterly), always labelled as
  AI on the page. The thread's `bot_state` becomes `answered` (`failed` on an unexpected error).
- The answer is short: at most `ANSWER_WORDS` (60) words (issue #20, D1 option A). The prompt
  asks for it; `submit_answer` rejects a longer answer once, so the model gets one repair turn
  (a second long answer ends the run and the deterministic search answers); the stored text is
  clipped to the limit as a last guard (`api.commons.words`).

The question, its details and the other replies are student writing: they reach the model only
inside `untrusted()` tags. With no model (off, failing, over budget) the answer is a
deterministic search of the catalog, the Commons and the campus guide, labelled "The AI is off;
here is what I found."

One run per question at a time: a Redis lock `commons:bot:{id}` (with a TTL) is taken before the
run; a second request while it is held gets a `busy` event and polls the thread instead.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from llm_gateway.api import (
    AgentError,
    AgentResult,
    AgentSpec,
    Budget,
    LLMUnavailableError,
    Message,
    SubmitTool,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from api.agents import live
from api.agents.ask import Citer
from api.agents.campus_tools import CampusTools, keywords, label, search_guide
from api.agents.live import LiveStep, course_codes_in, run_live
from api.agents.prompts import load_prompt
from api.agents.runtime import SSE_HEADERS, RunLog, sse
from api.agents.tools import untrusted
from api.auth.ratelimit import DAY, Limit, account_subject, ip_subject
from api.auth.store import Store
from api.commons import service
from api.commons.service import Viewer
from api.commons.words import ANSWER_WORDS, count_words, limit_words
from api.db import models as m
from api.repo import catalog as catalog_repo
from api.schemas.commons import (
    CommonsAnswerEvent,
    CommonsBotRequest,
    CommonsBusyEvent,
    CommonsCitation,
    CommonsDoneEvent,
    CommonsErrorEvent,
    CommonsStepEvent,
)

logger = logging.getLogger("api.agents")

TASK = "a9_commons_bot"
PROMPT = "a9_commons_bot"
BOT_TOOLS: tuple[str, ...] = (
    "search_courses",
    "get_course",
    "compare_courses",
    "get_program",
    "list_programs",
    "search_commons",
    "campus_guide",
)
# No forum tools: the answer is stored as a public reply (CC-1), and forum reviews are for
# logged-in readers only, so the bot never reads them, whoever triggered the run.
BOT_BUDGET = Budget(tool_calls=10, tokens=120_000, seconds=60)
#: The lock outlives the longest run (the budget's 60 s plus storing).
LOCK_TTL_S = 120
MAX_ANSWER_CHARS = 2400
MAX_CITATIONS = 10
OTHER_REPLIES = 4
REPLY_CHARS = 700
BODY_CHARS = 4000
FALLBACK_COURSES = 5
FALLBACK_THREADS = 3

#: Bot runs (not replays of a stored answer) per day.
BOT_PER_ACCOUNT = Limit("commons-bot:account", 40, DAY)
BOT_PER_IP = Limit("commons-bot:ip", 20, DAY)

BUSY = "The AI is already answering this question. Its answer will appear here in a moment."
FAILED = "The AI could not answer right now. Try again in a minute."
OFF = "The AI is off; here is what I found."


class CitationIn(BaseModel):
    kind: str
    id: str
    label: str = ""


class BotAnswer(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    citations: list[CitationIn] = Field(default=[], max_length=16)

    @field_validator("text")
    @classmethod
    def _short(cls, value: str) -> str:
        n = count_words(value)
        if n > ANSWER_WORDS:
            raise ValueError(
                f"the answer has {n} words; the limit is {ANSWER_WORDS}. Write a shorter answer"
            )
        return value


_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": f"Your answer in plain markdown (bold, a short list), at most "
            f"{ANSWER_WORDS} words.",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "course",
                            "program",
                            "thread",
                            "guide",
                            "post",
                            "summary",
                            "attribute",
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
}


def lock_key(thread_id: int) -> str:
    return f"commons:bot:{thread_id}"


# --------------------------------------------------------------------------- preparing a run


@dataclass
class BotRun:
    """What one POST .../bot will do: `replay` a stored answer, report `busy`, or `run`."""

    mode: Literal["replay", "busy", "run"]
    thread_id: int
    viewer: Viewer
    llm: object = None
    show_unpublished: bool = False
    #: The stored answer to send back (replay) or to rewrite (regenerate).
    existing_id: int | None = None
    #: The reply that summoned the bot (@quarterly).
    reply_to: int | None = None
    regenerate: bool = False
    log: RunLog = field(default_factory=RunLog)


_MD_LINK = re.compile(r"\[([^\]\n]{1,200})\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>", re.IGNORECASE)
_TRUSTED = re.compile(r"^https://([a-z0-9-]+\.)*uchicago\.edu(/|$)", re.IGNORECASE)


def _trusted_href(href: str) -> bool:
    return (href.startswith("/") and not href.startswith("//")) or bool(_TRUSTED.match(href))


def safe_answer(text: str) -> str:
    """The bot's answer as stored: links only to this site or to https uchicago.edu pages (the
    same rule as the Ask page), others reduced to their text, so a question cannot plant a link
    in a public AI answer; emails and phone numbers scrubbed like students' posts."""
    from api.forum.scrub import scrub

    def link(mt: re.Match[str]) -> str:
        return mt.group(0) if _trusted_href(mt.group(2)) else mt.group(1)

    def autolink(mt: re.Match[str]) -> str:
        return mt.group(0) if _trusted_href(mt.group(1)) else mt.group(1)

    return scrub(_AUTOLINK.sub(autolink, _MD_LINK.sub(link, text)))


def _bot_reply(db: Session, thread_id: int, parent_id: int | None) -> m.CommonsReply | None:
    parent = (
        m.CommonsReply.parent_id.is_(None)
        if parent_id is None
        else m.CommonsReply.parent_id == parent_id
    )
    return db.scalar(
        sa.select(m.CommonsReply)
        .where(
            m.CommonsReply.thread_id == thread_id,
            m.CommonsReply.kind == "bot",
            m.CommonsReply.status == "visible",
            parent,
        )
        .order_by(m.CommonsReply.id)
        .limit(1)
    )


def _summoned_reply(db: Session, thread: m.CommonsThread, reply_id: int) -> m.CommonsReply:
    reply = db.get(m.CommonsReply, reply_id)
    if reply is None or reply.thread_id != thread.id or reply.status != "visible":
        raise service.not_found("Reply")
    if reply.kind != "human" or not service.summons_bot(reply.body_md):
        raise HTTPException(
            status_code=422, detail="Only a reply that mentions @quarterly can call the AI."
        )
    return reply


def prepare(
    db: Session,
    store: Store,
    request: Request,
    viewer: Viewer,
    thread_id: int,
    body: CommonsBotRequest,
    *,
    llm: object,
    show_unpublished: bool,
) -> BotRun:
    """Checks, the replay shortcut, the lock and the rate limit, before the stream starts (so
    a 401/403/404/429 is a plain HTTP error, not an event)."""
    thread = service._visible_thread(db, thread_id)
    if body.regenerate or body.reply_to is not None:
        account = viewer.require()
        service.ensure_can_write(account)
    if body.regenerate and thread.author_ref != viewer.ref(thread.id):
        raise HTTPException(
            status_code=403, detail="Only the person who asked can ask the AI to answer again."
        )
    if body.reply_to is not None:
        _summoned_reply(db, thread, body.reply_to)
    existing = _bot_reply(db, thread.id, body.reply_to)
    base = BotRun(
        mode="run",
        thread_id=thread.id,
        viewer=viewer,
        llm=llm,
        show_unpublished=show_unpublished,
        existing_id=existing.id if existing else None,
        reply_to=body.reply_to,
        regenerate=body.regenerate and body.reply_to is None,
    )
    if existing is not None and not base.regenerate:
        base.mode = "replay"
        return base
    if store.incr(lock_key(thread.id), LOCK_TTL_S) > 1:
        base.mode = "busy"
        return base
    # Another run may have stored its answer between the check above and the lock: look again.
    again = _bot_reply(db, thread.id, body.reply_to)
    if again is not None and not base.regenerate:
        store.delete(lock_key(thread.id))
        base.existing_id = again.id
        base.mode = "replay"
        return base
    try:
        if viewer.account is not None:
            BOT_PER_ACCOUNT.hit(store, account_subject(viewer.account.id))
        else:
            BOT_PER_IP.hit(store, ip_subject(request))
    except HTTPException:
        store.delete(lock_key(thread.id))
        raise
    return base


# --------------------------------------------------------------------------------- the run


_MD_SPECIAL = re.compile(r"([\\`*_\[\]()<>#!|~])")


def _md(text: str) -> str:
    """Catalog text placed in markdown: special characters escaped."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(text.split()))


@dataclass
class BotHarness:
    db: Session
    run: BotRun

    @property
    def viewer(self) -> Viewer:
        return self.run.viewer

    def _thread(self) -> m.CommonsThread:
        return service._visible_thread(self.db, self.run.thread_id)

    # ---------------------------------------------------------------- context

    def _course(self, thread: m.CommonsThread) -> tuple[str, str] | None:
        if thread.course_id is None:
            return None
        course = self.db.get(m.Course, thread.course_id)
        return (course.code, course.title) if course is not None else None

    def context(self, thread: m.CommonsThread) -> str:
        """The user message: the question and the replies so far, as untrusted data."""
        lines = [f"A student asked this question in the Commons (thread:{thread.id})."]
        course = self._course(thread)
        if course is not None:
            lines.append(
                f"It is filed under the course {course[0]} ({course[1]}); read it with "
                "get_course before answering."
            )
        mentioned = course_codes_in(self.db, f"{thread.title}\n{thread.body_md}", limit=8)
        if course is not None:
            mentioned.pop(course[0], None)
        if mentioned:
            lines.append(
                "Courses it mentions that exist in the catalog: " + ", ".join(mentioned) + "."
            )
        text = thread.title + ("\n\n" + thread.body_md[:BODY_CHARS] if thread.body_md else "")
        lines += ["", "The question (title, then details):", untrusted(f"thread:{thread.id}", text)]
        replies = list(
            self.db.scalars(
                sa.select(m.CommonsReply)
                .where(
                    m.CommonsReply.thread_id == thread.id,
                    m.CommonsReply.kind == "human",
                    m.CommonsReply.status == "visible",
                )
                .order_by(m.CommonsReply.score.desc(), m.CommonsReply.id)
                .limit(OTHER_REPLIES)
            )
        )
        replies = [r for r in replies if r.id != self.run.reply_to]
        if replies:
            lines += [
                "",
                "Replies so far (context only: answer the question above, not these replies):"
                if self.run.reply_to is None
                else "Replies so far:",
            ]
            for r in replies:
                who = (
                    "the asker"
                    if r.author_ref and r.author_ref == thread.author_ref
                    else "a student"
                )
                lines.append(f"reply:{r.id} by {who}, score {r.score}:")
                lines.append(untrusted(f"reply:{r.id}", r.body_md[:REPLY_CHARS]))
        if self.run.reply_to is not None:
            summoner = self.db.get(m.CommonsReply, self.run.reply_to)
            if summoner is not None:
                if summoner.parent_id is not None:
                    parent = self.db.get(m.CommonsReply, summoner.parent_id)
                    if parent is not None and parent.status == "visible":
                        lines += ["", f"reply:{parent.id}, which the next reply answers:"]
                        lines.append(untrusted(f"reply:{parent.id}", parent.body_md[:REPLY_CHARS]))
                lines += [
                    "",
                    f"reply:{summoner.id} mentions you (@quarterly) and asks for your help. "
                    "Answer that reply, in the context of the question, in at most "
                    f"{ANSWER_WORDS} words:",
                    untrusted(f"reply:{summoner.id}", summoner.body_md[:REPLY_CHARS]),
                ]
        lines += ["", "Look up what you need, then call submit_answer."]
        return "\n".join(lines)

    def _system(self, tools: CampusTools) -> str:
        prompt = load_prompt(PROMPT)
        lines = [prompt.text, "", f"Today is {dt.date.today().isoformat()}."]
        if not tools.logged_in:
            lines.append(
                "Course reviews are not available to you: never say what students say about a "
                "course unless search_commons returned it."
            )
        return "\n".join(lines)

    # ---------------------------------------------------------------- citations

    def _cite(
        self, seen: set[str], cited: list[tuple[str, str]], thread_id: int
    ) -> list[CommonsCitation]:
        citer = Citer(self.db, seen)
        for kind, ident in cited:
            if kind == "thread" and ident.strip() == str(thread_id):
                continue  # the question itself
            citer.add(kind, ident)
        if citer.dropped:
            logger.warning(
                "%s: dropped %d citation(s) no tool returned in this run", TASK, citer.dropped
            )
        return [
            CommonsCitation.model_validate(
                {"kind": c.kind, "id": c.id, "label": c.label, "url": c.href}
            )
            for c in citer.kept[:MAX_CITATIONS]
        ]

    # ---------------------------------------------------------------- the model

    def _agent(
        self, thread: m.CommonsThread
    ) -> Iterator[CommonsStepEvent | tuple[str, list[CommonsCitation]]]:
        tools = CampusTools(self.db, account=None, show_unpublished=self.run.show_unpublished)
        prompt = load_prompt(PROMPT)
        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=self._system(tools),
            messages=[Message("user", self.context(thread))],
            tools=tools.tools(BOT_TOOLS),
            submit=SubmitTool(
                "submit_answer",
                "Your answer under the question, with citations.",
                BotAnswer,
                input_schema=_ANSWER_SCHEMA,
                strict=True,
            ),
            budget=BOT_BUDGET,
        )
        result: AgentResult[BotAnswer] | None = None
        for item in run_live(self.run.llm, spec, sink=self.run.log.sink, label=label):
            if isinstance(item, LiveStep):
                if item.status != "started":
                    self.run.log.step(item.tool, item.status)
                yield CommonsStepEvent(tool=item.tool, label=item.label, status=item.status)
            else:
                result = item
        if result is None:  # run_live ends with the result or raises
            raise AgentError("invalid_output", "no result")
        cited = [(c.kind, c.id) for c in result.output.citations]
        yield result.output.text.strip(), self._cite(result.seen_ids, cited, thread.id)

    # ---------------------------------------------------------------- without a model

    def fallback(self, thread: m.CommonsThread) -> tuple[str, list[CommonsCitation]]:
        """The catalog, the Commons and the campus guide, searched with the question's words."""
        text = f"{thread.title}\n{thread.body_md}"
        courses: dict[str, str] = {}
        own = self._course(thread)
        if own is not None:
            courses[own[0]] = own[1]
        for code, title in course_codes_in(self.db, text, limit=FALLBACK_COURSES).items():
            courses.setdefault(code, title)
        subjects = {c.split(" ")[0].lower() for c in courses}
        words = [w for w in keywords(text, limit=8) if not w.isdigit() and w not in subjects]
        queries = ([" ".join(words[:3])] if len(words) > 1 else []) + words[:4]
        for q in queries:
            if len(courses) >= FALLBACK_COURSES:
                break
            items, _ = catalog_repo.search_courses(
                self.db, live.CAMPUS_YEAR, q=q, limit=FALLBACK_COURSES
            )
            for c in items:
                if len(courses) < FALLBACK_COURSES:
                    courses.setdefault(c.code, c.title)
        threads = self._related(thread, words)
        guide = search_guide(text, limit=2)

        parts = [f"*{OFF}*"]
        if courses:
            parts.append("Courses that may help: " + ", ".join(f"**{c}**" for c in courses) + ".")
        if guide:
            parts.append("From the campus guide: " + "; ".join(_md(e.title) for e in guide) + ".")
        if threads:
            n = len(threads)
            parts.append(f"{n} related question{'s are' if n > 1 else ' is'} linked below.")
        if not courses and not guide and not threads:
            parts.append(
                "I found nothing in the catalog or the Commons for these words. Adding a course "
                "code (like MATH 15300) helps."
            )
        parts.append("Open a course page for details. Students' answers will appear below.")
        kept: list[str] = []
        for part in parts:  # the sources are also cited as chips, so a part may be left out
            if count_words("\n\n".join([*kept, part])) <= ANSWER_WORDS:
                kept.append(part)
        seen = {f"course:{c}" for c in courses}
        seen |= {f"guide:{e.id}" for e in guide} | {f"thread:{t}" for t in threads}
        cited = [("course", c) for c in courses]
        cited += [("guide", e.id) for e in guide] + [("thread", str(t)) for t in threads]
        return "\n\n".join(kept), self._cite(seen, cited, thread.id)

    def _related(self, thread: m.CommonsThread, words: list[str]) -> list[int]:
        t = m.CommonsThread
        hits = [
            sa.or_(t.title.icontains(w, autoescape=True), t.body_md.icontains(w, autoescape=True))
            for w in words[:5]
        ]
        if not hits and thread.course_id is None:
            return []
        same_course = t.course_id == thread.course_id if thread.course_id else sa.false()
        score = sum((sa.case((h, 1), else_=0) for h in hits), sa.literal(0))
        rows = self.db.execute(
            sa.select(t.id)
            .where(t.status == "visible", t.id != thread.id, sa.or_(same_course, score >= 2))
            .order_by((score + sa.case((same_course, 2), else_=0)).desc(), t.id.desc())
            .limit(FALLBACK_THREADS)
        ).all()
        return [int(r[0]) for r in rows]

    # ---------------------------------------------------------------- storing

    def store(
        self, thread: m.CommonsThread, text: str, citations: list[CommonsCitation]
    ) -> m.CommonsReply:
        text = limit_words(safe_answer(text))
        cites = [c.model_dump(exclude_none=True) for c in citations]
        reply: m.CommonsReply | None = None
        if self.run.regenerate and self.run.existing_id is not None:
            reply = self.db.get(m.CommonsReply, self.run.existing_id)
        if reply is not None:
            # A rewritten answer starts afresh: its old votes were for other words.
            self.db.execute(
                sa.delete(m.CommonsVote).where(
                    m.CommonsVote.target_type == "reply", m.CommonsVote.target_id == reply.id
                )
            )
            reply.body_md = text
            reply.citations = cites
            reply.score = 0
            reply.edited_day = service.today()
        else:
            parent_id, depth = service.place_under(self.db, thread, self.run.reply_to)
            reply = m.CommonsReply(
                thread_id=thread.id,
                parent_id=parent_id,
                depth=depth,
                author_ref=None,
                kind="bot",
                body_md=text,
                citations=cites,
                status="visible",
            )
            self.db.add(reply)
            self.db.flush()
            thread.last_reply_id = reply.id
        if self.run.reply_to is None:
            thread.bot_state = "answered"
        return reply

    def _record(self, ok: bool) -> None:
        if not self.run.log.records:
            return
        run = m.AgentRun(
            kind="commons_bot",
            plan_id=None,
            model="none",
            status="ok" if ok else "failed",
            created_day=dt.date.today(),
        )
        self.db.add(run)
        self.db.flush()
        self.run.log.save(self.db, run)

    def _out(self, reply: m.CommonsReply, thread: m.CommonsThread) -> CommonsAnswerEvent:
        out = service.reply_out(
            self.db,
            reply,
            thread=thread,
            handles={},
            ref=self.viewer.ref(thread.id),
        )
        return CommonsAnswerEvent(reply=out)

    def events(self) -> Iterator[BaseModel]:
        thread = self._thread()
        answer: tuple[str, list[CommonsCitation]] | None = None
        used_ai = False
        try:
            for item in self._agent(thread):
                if isinstance(item, CommonsStepEvent):
                    yield item
                else:
                    answer = item
                    used_ai = True
        except (AgentError, LLMUnavailableError) as exc:
            reason = getattr(exc, "reason", type(exc).__name__)
            logger.info("%s: no answer (%s); deterministic search instead", TASK, reason)
        thread = self._thread()  # the run used the session in its own thread
        if answer is None:
            answer = self.fallback(thread)
        reply = self.store(thread, *answer)
        self._record(used_ai)
        self.db.commit()
        self.db.refresh(reply)
        event = self._out(reply, thread)
        event.fallback = not used_ai
        yield event
        yield CommonsDoneEvent()


# ------------------------------------------------------------------------------- streaming


def _replay(db: Session, run: BotRun) -> Iterator[BaseModel]:
    thread = service._visible_thread(db, run.thread_id)
    reply = db.get(m.CommonsReply, run.existing_id) if run.existing_id else None
    if reply is not None:
        out = service.reply_out(db, reply, thread=thread, handles={}, ref=run.viewer.ref(thread.id))
        votes = service._my_votes(
            db, run.viewer, "reply", {reply.id: r} if (r := run.viewer.ref(thread.id)) else {}
        )
        out.my_vote = votes.get(reply.id, 0)  # type: ignore[assignment]
        yield CommonsAnswerEvent(reply=out)
    yield CommonsDoneEvent()


def _mark_failed(db: Session, thread_id: int, run: BotRun) -> None:
    if run.reply_to is not None:
        return
    try:
        db.execute(
            sa.update(m.CommonsThread)
            .where(m.CommonsThread.id == thread_id, m.CommonsThread.bot_state == "pending")
            .values(bot_state="failed")
        )
        db.commit()
    except Exception:  # the stream already reports the failure
        db.rollback()


def events(db: Session, store: Store, run: BotRun) -> Iterator[BaseModel]:
    if run.mode == "replay":
        yield from _replay(db, run)
        return
    if run.mode == "busy":
        yield CommonsBusyEvent(message=BUSY)
        yield CommonsDoneEvent()
        return
    try:
        yield from BotHarness(db, run).events()
    finally:
        store.delete(lock_key(run.thread_id))


def stream(db: Session, store: Store, run: BotRun) -> StreamingResponse:
    def body() -> Iterator[str]:
        try:
            for event in events(db, store, run):
                yield sse(event)
        except Exception:
            logger.exception("%s: run failed", TASK)  # no request data in the message
            db.rollback()
            _mark_failed(db, run.thread_id, run)
            yield sse(CommonsErrorEvent(message=FAILED))

    return StreamingResponse(body(), media_type="text/event-stream", headers=SSE_HEADERS)
