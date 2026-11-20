"""A5 campus ask: the Ask page's chatbot and the companion's chat (docs/BEST-OF-UCHICAGO-PLAN.md).

One run: the student's message (scrubbed of emails and phone numbers) and the last turns of the
conversation go to the model with the campus read tools (`api.agents.campus_tools`); each tool
call is streamed as a `step` while the model works (`run_live`); the model ends with
`submit_answer` {text, citations, followups}. Citations whose id no tool returned in this run
are dropped and every chip's label and link are built here from the id. The `courses` of the
answer are the real courses the text mentions or cites (checked against the catalog).

With no model (not configured, failed, over budget) the answer is a deterministic search of the
catalog, the forum questions and the campus guide, so the student always gets something useful.
Nothing is stored but the run's cost record (`agent_run` kind `ask`, `llm_call`): conversations
live in the browser.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from itertools import pairwise
from typing import Any, get_args
from urllib.parse import quote

import sqlalchemy as sa
from llm_gateway.api import (
    AgentError,
    AgentResult,
    AgentSpec,
    Budget,
    LLMUnavailableError,
    Message,
    SubmitTool,
    Tool,
    ToolOutput,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.agents import live
from api.agents.campus_tools import (
    CAMPUS_TOOLS,
    CampusTools,
    guide_entry,
    keywords,
    label,
    search_guide,
)
from api.agents.live import LiveStep, course_codes_in, known_courses, normalize_code, run_live
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog
from api.agents.tools import untrusted
from api.db import models as m
from api.forum.scrub import scrub
from api.repo import catalog as catalog_repo
from api.schemas.ask import (
    AskAnswerEvent,
    AskCitation,
    AskCitationKind,
    AskCourse,
    AskDoneEvent,
    AskRequest,
    AskStepEvent,
)

logger = logging.getLogger("api.agents")

TASK = "a5_campus_ask"
PROMPT = "a5_ask"
#: The hard limits of a run. Past `SOFT_TOOL_CALLS` every tool answers "answer now" instead,
#: so a curious model still ends with an answer rather than the budget's error.
ASK_BUDGET = Budget(tool_calls=14, tokens=160_000, seconds=75)
SOFT_TOOL_CALLS = 8
ENOUGH = (
    "You have used the tool calls this answer may make. Do not call more tools: call "
    "submit_answer now with what you already found."
)
HISTORY_TURNS = 10
MAX_ANSWER_CHARS = 3000
MAX_CITATIONS = 12
MAX_COURSES = 12
MAX_FOLLOWUPS = 3
FALLBACK_COURSES = 5

KINDS: tuple[str, ...] = get_args(AskCitationKind)

RESTING = "The AI guide is resting right now, but here is what I found:"
NOTHING = (
    "The AI guide is resting right now, and I found nothing in the catalog, the forum or the "
    "campus guide for those words. Try a course code (like MATH 15100), a subject (like "
    "economics) or a topic (like the Core or study abroad)."
)
GREETING = (
    "Hi! I'm Quarterly's campus guide. Ask me about courses, the Core, majors and minors, what "
    "students say about a class, or life in the College, and I'll look it up for you."
)
GENERIC_FOLLOWUPS = [
    "What is the Core curriculum?",
    "How do I choose a major?",
    "What should a first-year take in Autumn?",
]
_GREETING = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|howdy|good (morning|afternoon|evening)|thanks|thank you|"
    r"thx|ty)( there| quarterly| guide)?\s*[!.?]*\s*$",
    re.IGNORECASE,
)


class CitationIn(BaseModel):
    kind: str
    id: str
    label: str = ""


class AskAnswer(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    citations: list[CitationIn] = []
    followups: list[str] = []


_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "Your reply (markdown subset), at most 180 words.",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["kind", "id", "label"],
                "additionalProperties": False,
            },
        },
        "followups": {
            "type": "array",
            "description": "Up to three short follow-up questions in the student's voice.",
            "items": {"type": "string"},
        },
    },
    "required": ["text", "citations", "followups"],
    "additionalProperties": False,
}


def capped(tools: list[Tool], limit: int) -> list[Tool]:
    """`tools` sharing one counter: after `limit` calls each returns `ENOUGH` as an error."""
    used = [0]

    def wrap(tool: Tool) -> Tool:
        def handler(args: dict[str, Any]) -> ToolOutput:
            used[0] += 1
            if used[0] > limit:
                return ToolOutput(ENOUGH, is_error=True)
            return tool.handler(args)

        return replace(tool, handler=handler)

    return [wrap(t) for t in tools]


#: Words that name a part of the Core, and the catalog's `core_tags` value for it.
CORE_WORDS: dict[str, str] = {
    "humanities": "humanities",
    "hum": "humanities",
    "civ": "civilization",
    "civilization": "civilization",
    "arts": "arts",
    "biology": "biological_sciences",
    "biological": "biological_sciences",
    "physical": "physical_sciences",
    "physics": "physical_sciences",
    "chemistry": "physical_sciences",
    "mathematical": "mathematical_sciences",
    "sosc": "social_sciences",
    "social": "social_sciences",
}


def core_tag_of(message: str) -> str | None:
    """The Core area a question is about ("a Core humanities sequence"), if it says one."""
    text = message.lower()
    if not re.search(r"\b(core|gen ?ed|general education|requirement|sequence)\b", text):
        return None
    for word, tag in CORE_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return tag
    return None


def course_href(code: str) -> str:
    return f"/courses/{quote(code, safe='')}"


def page_href(code: str, slug: str) -> str:
    return f"{course_href(code)}/i/{quote(slug, safe='')}"


# --------------------------------------------------------------------- citations


@dataclass
class Citer:
    """Checks citations against the ids the run saw and builds their chips from the database."""

    db: Session
    seen: set[str]
    kept: list[AskCitation] = field(default_factory=list)
    dropped: int = 0

    def add(self, kind: str, ident: str) -> None:
        ident = ident.strip()
        if kind == "course":
            ident = normalize_code(ident) or ident
        if kind not in KINDS or f"{kind}:{ident}" not in self.seen:
            self.dropped += 1
            return
        if any((c.kind, c.id) == (kind, ident) for c in self.kept):
            return
        chip = self._chip(kind, ident)
        if chip is None:
            self.dropped += 1
        elif len(self.kept) < MAX_CITATIONS:
            self.kept.append(chip)

    def _chip(self, kind: str, ident: str) -> AskCitation | None:
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
                label, href = f"Forum: {_clip(title, 60)}", f"/forum/t/{ident}"
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
        return AskCitation.model_validate(
            {"kind": kind, "id": ident, "label": _clip(label, 90), "href": href}
        )

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


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def answer_courses(db: Session, text: str, citations: Iterable[AskCitation]) -> list[AskCourse]:
    """The real courses `text` mentions, then the cited ones, at most 12."""
    found = course_codes_in(db, text, limit=MAX_COURSES)
    cited = [
        c.id if c.kind == "course" else c.id.rpartition(":")[0]
        for c in citations
        if c.kind in ("course", "attribute")
    ]
    extra = known_courses(db, [c for c in cited if c not in found])
    for code in cited:
        if code in extra and code not in found:
            found[code] = extra[code]
    return [AskCourse(code=c, title=t) for c, t in list(found.items())[:MAX_COURSES]]


def clean_followups(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in items:
        text = _clip(scrub(str(raw)), 120)
        if text and text not in out:
            out.append(text)
    return out[:MAX_FOLLOWUPS]


# --------------------------------------------------------------------- the run


@dataclass
class AskRun:
    db: Session
    llm: object
    req: AskRequest
    account: m.Account | None
    show_unpublished: bool
    log: RunLog = field(default_factory=RunLog)
    run_id: str = ""
    #: Set once the answer came from the model (for the run record).
    used_ai: bool = False

    def events(self) -> Iterator[BaseModel]:
        message = scrub(self.req.message.strip())
        answer: AskAnswerEvent | None = None
        if _GREETING.match(message) and not self.req.history:
            answer = self._greeting()
        else:
            try:
                for item in self._agent(message):
                    if isinstance(item, AskStepEvent):
                        yield item
                    else:
                        answer = item
            except (AgentError, LLMUnavailableError) as exc:
                reason = getattr(exc, "reason", type(exc).__name__)
                logger.info("%s: no answer (%s); deterministic search instead", TASK, reason)
        if answer is None:
            answer = self.fallback(message)
        yield answer
        yield self._finish()

    # ---------------------------------------------------------------- model

    def _system(self, tools: CampusTools) -> str:
        prompt = load_prompt(PROMPT)
        lines = [prompt.text, "", f"Today is {dt.date.today().isoformat()}."]
        if self.req.mode == "companion":
            lines.append(
                "You are answering in the companion, a small side panel: keep it to 110 words."
            )
        if tools.logged_in:
            lines.append(
                "The student is logged in: you may call get_profile to personalise the answer."
            )
        else:
            lines.append(
                "The student is not logged in: forum reviews and their profile are not "
                "available. If it would help, suggest logging in and building a dashboard "
                "(/me)."
            )
        context = self._context()
        if context:
            lines += ["", "Where the student is asking from:", *context]
        return "\n".join(lines)

    def _context(self) -> list[str]:
        ctx = self.req.context
        out: list[str] = []
        if ctx.page:
            page = re.sub(r"[^\w/%\-.:?=&#]", "", ctx.page)[:200]
            out.append(f"- They are on the page {page}.")
        code = normalize_code(ctx.course_code or "")
        if code:
            title = known_courses(self.db, [code]).get(code)
            if title:
                out.append(
                    f"- The page is about {code} ({title}). Questions like “this course” "
                    "mean it; read it with get_course before answering."
                )
        if ctx.thread_id:
            row = self.db.execute(
                sa.select(m.CommonsThread.title).where(
                    m.CommonsThread.id == ctx.thread_id, m.CommonsThread.status == "visible"
                )
            ).first()
            if row is not None:
                out.append(f"- The page is forum question thread:{ctx.thread_id}, titled:")
                out.append(untrusted(f"thread:{ctx.thread_id}", _clip(row[0], 200)))
        return out

    def _history(self) -> list[Message]:
        turns = [Message(t.role, scrub(t.text)) for t in self.req.history if t.text.strip()]
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

    def _agent(self, message: str) -> Iterator[AskStepEvent | AskAnswerEvent]:
        tools = CampusTools(self.db, account=self.account, show_unpublished=self.show_unpublished)
        prompt = load_prompt(PROMPT)
        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=self._system(tools),
            messages=[*self._history(), Message("user", message)],
            tools=capped(tools.tools(CAMPUS_TOOLS), SOFT_TOOL_CALLS),
            submit=SubmitTool(
                "submit_answer",
                "Your reply to the student, with citations and follow-up questions.",
                AskAnswer,
                input_schema=_ANSWER_SCHEMA,
                strict=True,
            ),
            budget=ASK_BUDGET,
        )
        result: AgentResult[AskAnswer] | None = None
        for item in run_live(self.llm, spec, sink=self.log.sink, label=label):
            if isinstance(item, LiveStep):
                if item.status != "started":
                    self.log.step(item.tool, item.status)
                yield AskStepEvent(tool=item.tool, label=item.label, status=item.status)
            else:
                result = item
        if result is None:  # run_live always ends with the result or raises
            raise AgentError("invalid_output", "no result")
        citer = Citer(self.db, result.seen_ids)
        for c in result.output.citations:
            citer.add(c.kind, c.id)
        if citer.dropped:
            logger.warning(
                "%s: dropped %d citation(s) no tool returned in this run", TASK, citer.dropped
            )
        text = result.output.text.strip()
        self.used_ai = True
        yield AskAnswerEvent(
            text=text,
            citations=citer.kept,
            courses=answer_courses(self.db, text, citer.kept),
            followups=clean_followups(result.output.followups),
        )

    # ---------------------------------------------------------------- without a model

    def _greeting(self) -> AskAnswerEvent:
        return AskAnswerEvent(text=GREETING, followups=GENERIC_FOLLOWUPS, ai=False)

    def fallback(self, message: str) -> AskAnswerEvent:
        """The catalog, the forum questions and the campus guide, searched with the message's
        words: always a useful answer, never an error."""
        courses = self._fallback_courses(message)
        guide = search_guide(message, limit=2)
        threads = self._fallback_threads(message)
        if not courses and not guide and not threads:
            return AskAnswerEvent(text=NOTHING, followups=GENERIC_FOLLOWUPS, ai=False)
        parts = [RESTING]
        seen: set[str] = set()
        if courses:
            parts.append(
                "**Courses**\n" + "\n".join(f"- {code}: {title}" for code, title in courses)
            )
            seen |= {f"course:{code}" for code, _ in courses}
        if guide:
            parts.append(
                "**From the campus guide**\n"
                + "\n".join(f"- *{e.title}*: {_first_sentence(e.text)}" for e in guide)
            )
            seen |= {f"guide:{e.id}" for e in guide}
        if threads:
            parts.append(
                "**Asked on the forum**\n"
                + "\n".join(f"- [{_link_text(title)}](/forum/t/{tid})" for tid, title in threads)
            )
            seen |= {f"thread:{tid}" for tid, _ in threads}
        parts.append("Open a course for its description, requirements and what students say.")
        citer = Citer(self.db, seen)
        for code, _ in courses:
            citer.add("course", code)
        for e in guide:
            citer.add("guide", e.id)
        for tid, _ in threads:
            citer.add("thread", str(tid))
        text = "\n\n".join(parts)
        return AskAnswerEvent(
            text=text,
            citations=citer.kept,
            courses=[AskCourse(code=c, title=t) for c, t in courses],
            followups=GENERIC_FOLLOWUPS,
            ai=False,
        )

    def _fallback_courses(self, message: str) -> list[tuple[str, str]]:
        """Courses the message names, then catalog matches: for a question about a part of the
        Core, that part's courses (matching the other words first); then the whole phrase,
        adjacent word pairs, and single words from the rarest (the most telling) up."""
        found: dict[str, str] = dict(course_codes_in(self.db, message, limit=FALLBACK_COURSES))
        words = keywords(message)
        year = live.CAMPUS_YEAR
        tag = core_tag_of(message)
        if tag:
            rest = [w for w in words if w not in CORE_WORDS and w != "core"]
            for q in [*rest, None]:
                items, _ = catalog_repo.search_courses(
                    self.db, year, q=q, core_tag=tag, limit=FALLBACK_COURSES
                )
                for c in items:
                    if c.code not in found and len(found) < FALLBACK_COURSES:
                        found[c.code] = c.title
            if len(found) >= FALLBACK_COURSES:
                return list(found.items())
        totals = {w: catalog_repo.search_courses(self.db, year, q=w, limit=1)[1] for w in words}
        singles = sorted((w for w in words if totals[w]), key=lambda w: totals[w])
        queries = [" ".join(words)] if len(words) > 2 else []
        queries += [f"{a} {b}" for a, b in pairwise(words)]
        named = len(found)
        wanted = FALLBACK_COURSES * 2
        for q in [*queries, *singles]:
            if len(found) >= wanted:
                break
            items, _ = catalog_repo.search_courses(self.db, year, q=q, limit=wanted)
            for c in items:
                if c.code not in found and len(found) < wanted:
                    found[c.code] = c.title
        rows = list(found.items())
        # Named courses first; then College-level courses before graduate ones (30000 and up).
        later = sorted(rows[named:], key=lambda r: r[0].split(" ")[-1] >= "30000")
        return (rows[:named] + later)[:FALLBACK_COURSES]

    def _fallback_threads(self, message: str) -> list[tuple[int, str]]:
        """Forum questions that share the most words with the message (at least two, or the
        only one the message has)."""
        words = keywords(message, limit=5)
        if not words:
            return []
        thread = m.CommonsThread
        rows = self.db.execute(
            sa.select(thread.id, thread.title, thread.body_md)
            .where(
                thread.status == "visible",
                sa.or_(
                    *(
                        sa.or_(
                            thread.title.icontains(w, autoescape=True),
                            thread.body_md.icontains(w, autoescape=True),
                        )
                        for w in words
                    )
                ),
            )
            .order_by(thread.id.desc())
            .limit(40)
        ).all()
        need = min(2, len(words))
        scored = []
        for tid, title, body in rows:
            hay_title, hay_body = title.lower(), body.lower()
            hits = sum(1 for w in words if w in hay_title or w in hay_body)
            if hits >= need:
                bonus = sum(1 for w in words if w in hay_title)
                scored.append((hits + bonus, int(tid), str(title)))
        scored.sort(key=lambda s: (-s[0], -s[1]))
        return [(tid, title) for _, tid, title in scored[:3]]

    # ---------------------------------------------------------------- record

    def _finish(self) -> AskDoneEvent:
        run_id = str(uuid.uuid4())
        if self.log.records:
            run = m.AgentRun(
                kind="ask",
                plan_id=None,
                model="none",
                status="ok" if self.used_ai else "failed",
                created_day=dt.date.today(),
            )
            self.db.add(run)
            self.db.flush()
            self.log.save(self.db, run)
            run_id = str(run.id)
        self.db.commit()
        return AskDoneEvent(run_id=run_id)


def _first_sentence(text: str) -> str:
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return match.group(1) if match else text


def _link_text(title: str) -> str:
    """A forum title as markdown link text: brackets and the like removed."""
    return _clip(re.sub(r"[\[\]()<>*_`\\]", "", scrub(title)), 80) or "A forum question"
