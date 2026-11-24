"""A6 the interviewing guide (`POST /agents/interview`, docs/BEST-OF-UCHICAGO-PLAN.md).

One turn: the student's profile (as data), the conversation so far and their newest answer go to
the model with two catalog tools; each tool call streams as a `step`; the model ends with
`submit_turn` {text, quick_replies, topic, facts, portrait, done}. The server then keeps only the
facts the student actually said in this conversation (each list item must share a word with the
student's own messages), merges list facts with the profile, checks that every course the text
names exists, and computes the progress itself. Nothing is written: the browser saves what the
student keeps with PATCH /me/profile.

Without a model (not configured, failed, over budget, over the daily limit) a deterministic guide
asks the same questions in the same order, extracts facts from the answer with simple rules and
writes a template portrait at the end. The `welcome_back` greeting is cached for a few hours per
profile, so returning to the dashboard does not call the model each time.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, cast, get_args

from llm_gateway.api import AgentError, AgentResult, AgentSpec, Budget, Message, SubmitTool
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from api.agents.campus_tools import CampusTools, label
from api.agents.live import LiveStep, course_codes_in, run_live
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog
from api.agents.tools import untrusted
from api.auth.store import Store
from api.db import models as m
from api.forum.scrub import scrub
from api.profile_data import memory_of, portrait_of, profile_brief, sections_filled
from api.schemas.profile import (
    MAX_ITEMS,
    TOPICS,
    CourseMention,
    DashboardStepEvent,
    HumanitiesGoal,
    InterviewRequest,
    InterviewTurn,
    InterviewTurnEvent,
    Portrait,
    ProfileDoneEvent,
    ProfilePatch,
    Topic,
    Workload,
)

logger = logging.getLogger("api.agents")

TASK = "a6_interview"
PROMPT = "a6_interview"
BUDGET = Budget(tool_calls=4, tokens=90_000, seconds=45)
TOOLS = ("search_courses", "get_course")
HISTORY_TURNS = 16
MAX_WORDS = 160
WELCOME_TTL_S = 6 * 3600

#: The topics with a section on the dashboard (wrap-up excluded), in interview order.
MAIN: tuple[Topic, ...] = TOPICS[:-1]
SECTION_OF: dict[str, Topic] = {
    "class_year": "class_year",
    "interests": "interests",
    "humanities": "humanities",
    "research": "research",
    "career": "career",
    "future": "future",
    "constraints": "constraints",
}
TOPIC_LABELS: dict[Topic, str] = {
    "class_year": "your class year",
    "interests": "your interests",
    "humanities": "the humanities",
    "research": "research",
    "career": "your career plans",
    "future": "where you're heading",
    "constraints": "workload and constraints",
    "wrapup": "your portrait",
}
GOALS: tuple[str, ...] = get_args(HumanitiesGoal)
WORKLOADS: tuple[str, ...] = get_args(Workload)

NO_AI_NOTE = "Your guide is running without the AI right now; it asks the same questions."


# ------------------------------------------------------------------------------ payloads


def _clip(value: object, n: int) -> object:
    return " ".join(value.split())[:n] if isinstance(value, str) else value


def _clip_list(value: object, n: int, size: int) -> object:
    if not isinstance(value, list):
        return value
    out = [" ".join(str(v).split())[:size] for v in value if str(v).strip()]
    return out[:n]


class Facts(BaseModel):
    """What the guide noted from the student's messages (lists: new items only)."""

    class_year: int | None = None
    interests: list[str] = []
    research_areas: list[str] = []
    humanities_goal: HumanitiesGoal | None = None
    humanities_topics: list[str] = []
    humanities_note: str | None = None
    career_plans: str | None = None
    career_paths: list[str] = []
    future_domains: list[str] = []
    constraints: list[str] = []
    workload: Workload | None = None

    @field_validator(
        "interests",
        "research_areas",
        "humanities_topics",
        "career_paths",
        "future_domains",
        "constraints",
        mode="before",
    )
    @classmethod
    def _lists(cls, value: object) -> object:
        return _clip_list(value, 12, 60)

    @field_validator("humanities_note", "career_plans", mode="before")
    @classmethod
    def _texts(cls, value: object) -> object:
        return _clip(value, 600) or None

    @field_validator("class_year", mode="before")
    @classmethod
    def _year(cls, value: object) -> object:
        if isinstance(value, int | float) and not 2020 <= int(value) <= 2040:
            return None
        return value

    @field_validator("humanities_goal", mode="before")
    @classmethod
    def _goal(cls, value: object) -> object:
        return value if value in GOALS else None

    @field_validator("workload", mode="before")
    @classmethod
    def _workload(cls, value: object) -> object:
        return value if value in WORKLOADS else None


class PortraitDraft(BaseModel):
    headline: str = ""
    summary: str = ""
    themes: list[str] = []

    @field_validator("headline", mode="before")
    @classmethod
    def _headline(cls, value: object) -> object:
        return _clip(value, 90)

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, value: object) -> object:
        return _clip(value, 400)

    @field_validator("themes", mode="before")
    @classmethod
    def _themes(cls, value: object) -> object:
        return _clip_list(value, 6, 40)


class TurnPayload(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    quick_replies: list[str] = []
    topic: Topic
    facts: Facts = Facts()
    portrait: PortraitDraft | None = None
    done: bool = False

    @field_validator("quick_replies", mode="before")
    @classmethod
    def _chips(cls, value: object) -> object:
        return _clip_list(value, 6, 48)


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable_enum(*values: str) -> dict[str, Any]:
    return {"anyOf": [{"type": "string", "enum": list(values)}, {"type": "null"}]}


_LIST = {"type": "array", "items": {"type": "string"}}
_NULL_STR = {"type": ["string", "null"]}
TURN_SCHEMA = _obj(
    {
        "text": {"type": "string", "description": "Your message: under 120 words, one question."},
        "quick_replies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Two to six short answers the student can tap (2-5 words each).",
        },
        "topic": {"type": "string", "enum": list(TOPICS)},
        "facts": _obj(
            {
                "class_year": {"type": ["integer", "null"]},
                "interests": _LIST,
                "research_areas": _LIST,
                "humanities_goal": _nullable_enum(*GOALS),
                "humanities_topics": _LIST,
                "humanities_note": _NULL_STR,
                "career_plans": _NULL_STR,
                "career_paths": _LIST,
                "future_domains": _LIST,
                "constraints": _LIST,
                "workload": _nullable_enum(*WORKLOADS),
            }
        ),
        "portrait": {
            "anyOf": [
                _obj(
                    {
                        "headline": {"type": "string"},
                        "summary": {"type": "string"},
                        "themes": _LIST,
                    }
                ),
                {"type": "null"},
            ]
        },
        "done": {"type": "boolean"},
    }
)


# ------------------------------------------------------------------------------ context


def academic_start(today: dt.date | None = None) -> int:
    """The calendar year the current academic year started in (Nov 2026 -> 2026)."""
    day = today or dt.date.today()
    return day.year if day.month >= 7 else day.year - 1


@dataclass
class Context:
    row: m.StudentProfile
    username: str
    req: InterviewRequest
    message: str = ""
    history: list[InterviewTurn] = field(default_factory=list)

    @classmethod
    def build(cls, row: m.StudentProfile, username: str, req: InterviewRequest) -> Context:
        history = [
            t.model_copy(update={"text": scrub(t.text.strip())})
            for t in req.history[-HISTORY_TURNS:]
            if t.text.strip()
        ]
        message = scrub(" ".join((req.message or "").split()))
        return cls(row=row, username=username, req=req, message=message, history=history)

    @property
    def mode(self) -> str:
        if self.req.mode == "reply" and not self.message:
            return "start"
        return self.req.mode

    def student_text(self) -> str:
        """Everything the student wrote in this conversation."""
        said = [t.text for t in self.history if t.role == "student"]
        if self.message:
            said.append(self.message)
        return "\n".join(said)

    def answering(self) -> Topic | None:
        """The topic of the guide's last question (what the newest message answers)."""
        for turn in reversed(self.history):
            if turn.role == "guide":
                return turn.topic
        return None

    def asked(self, topic: Topic) -> int:
        """How many times the guide asked about `topic` in this conversation."""
        return sum(1 for t in self.history if t.role == "guide" and t.topic == topic)

    def covered(self, patch: ProfilePatch | None = None) -> list[Topic]:
        """Main topics with an answer: filled in the profile (or in `patch`), marked covered
        earlier, or answered in this conversation."""
        filled = sections_filled(self.row)
        # The humanities count only once the goal is known (just to pass, or to enjoy what?).
        filled["humanities"] = self.row.humanities_goal is not None
        done: set[str] = {SECTION_OF[k] for k, v in filled.items() if v}
        done |= set(memory_of(self.row).covered)
        answered: Topic | None = None
        for turn in self.history:
            if turn.role == "guide":
                answered = turn.topic
            elif answered is not None:
                done.add(answered)
        if self.mode == "reply" and self.answering() is not None:
            done.add(cast(str, self.answering()))
        if patch is not None:
            sent = patch.model_fields_set
            pairs = {
                "class_year": "class_year",
                "interests": "interests",
                "humanities_goal": "humanities",
                "research_areas": "research",
                "career_plans": "career",
                "career_paths": "career",
                "future_domains": "future",
                "constraints": "constraints",
                "workload": "constraints",
            }
            done |= {topic for name, topic in pairs.items() if name in sent}
        return [t for t in MAIN if t in done]

    def next_topic(self, patch: ProfilePatch | None = None) -> Topic:
        covered = self.covered(patch)
        return next((t for t in MAIN if t not in covered), "wrapup")


def progress_of(covered: Sequence[Topic], done: bool) -> float:
    return 1.0 if done else round(len([t for t in covered if t in MAIN]) / len(MAIN), 3)


# ------------------------------------------------------------------------------ facts


_STOP = frozenset(
    {
        *("the", "and", "for", "with", "about", "into", "from", "that", "this", "what"),
        *("want", "like", "love", "really", "just", "some", "maybe", "also", "very", "much"),
        *("more", "most", "things", "stuff", "kind", "sort"),
    }
)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


def grounded(item: str, said: str) -> bool:
    """Whether the student's own words support `item`: one of its words (or its acronym, like
    "AI" or "ML") appears in what they wrote. Words are compared by their first 5 letters, so
    "philosophy" matches "philosophical"."""
    text = said.casefold()
    words = _words(item)
    significant = [w for w in words if len(w) >= 3 and w not in _STOP] or words
    for word in significant:
        stem = word[:5]
        if len(stem) <= 3:
            if re.search(rf"\b{re.escape(stem)}\b", text):
                return True
        elif stem in text:
            return True
    initials = "".join(w[0] for w in words if w)
    return len(initials) >= 2 and re.search(rf"\b{re.escape(initials)}\b", text) is not None


_YEAR_WORDS = re.compile(
    r"\b(20[2-4]\d|'\d\d|first[- ]?year|second[- ]?year|third[- ]?year|fourth[- ]?year|"
    r"freshman|sophomore|junior|senior|class of)\b",
    re.IGNORECASE,
)


def _merge(existing: Sequence[str], new: Sequence[str]) -> list[str] | None:
    """`existing` plus the items of `new` it lacks (case-insensitive); None when nothing is new."""
    have = {e.casefold() for e in existing}
    added = [n for n in new if n.casefold() not in have]
    if not added:
        return None
    merged = list(existing)
    for item in added:
        if len(merged) >= MAX_ITEMS:
            break
        merged.append(item)
        have.add(item.casefold())
    return merged


LIST_FACTS = (
    "interests",
    "research_areas",
    "humanities_topics",
    "career_paths",
    "future_domains",
    "constraints",
)


def proposed_patch(
    ctx: Context, facts: Facts, portrait: PortraitDraft | None = None
) -> tuple[ProfilePatch, int]:
    """The facts as a profile patch, keeping only what the student's own words support, with
    list facts merged into the profile's lists. Returns the patch and how many facts were
    dropped as unsupported."""
    said = ctx.student_text()
    topics_seen = {t.topic for t in ctx.history if t.role == "guide"} | {ctx.answering()}
    data: dict[str, Any] = {}
    dropped = 0
    row = ctx.row
    if facts.class_year is not None:
        if _YEAR_WORDS.search(said) and facts.class_year != row.class_year:
            data["class_year"] = facts.class_year
        elif not _YEAR_WORDS.search(said):
            dropped += 1
    for name in LIST_FACTS:
        new: list[str] = []
        for item in getattr(facts, name):
            item = scrub(item.strip())
            if not item:
                continue
            if grounded(item, said):
                new.append(item)
            else:
                dropped += 1
        merged = _merge(list(getattr(row, name)), new)
        if merged is not None:
            data[name] = merged
    if facts.humanities_goal is not None and facts.humanities_goal != row.humanities_goal:
        if "humanities" in topics_seen or re.search(r"humanit|core", said, re.IGNORECASE):
            data["humanities_goal"] = facts.humanities_goal
        else:
            dropped += 1
    if facts.workload is not None and facts.workload != row.workload:
        if "constraints" in topics_seen or re.search(
            r"light|balanc|intense|heavy|easy|hard|chill|busy|manageable|workload",
            said,
            re.IGNORECASE,
        ):
            data["workload"] = facts.workload
        else:
            dropped += 1
    for name, topic in (("humanities_note", "humanities"), ("career_plans", "career")):
        value = getattr(facts, name)
        if value and value != getattr(row, name):
            if topic in topics_seen and said.strip():
                data[name] = value[:1200]
            else:
                dropped += 1
    if portrait is not None and (portrait.headline or portrait.summary):
        data["portrait"] = Portrait(
            headline=portrait.headline, summary=portrait.summary, themes=portrait.themes[:6]
        )
    try:
        return ProfilePatch.model_validate(data), dropped
    except ValidationError:
        logger.warning("%s: a proposed patch did not validate", TASK)
        return ProfilePatch(), dropped + len(data)


# ------------------------------------------------------------------------------ the rules


def _split(text: str) -> list[str]:
    """An answer cut into short items: "physics, film and Greek tragedy" -> 3 items."""
    text = re.sub(
        r"^(i(?:'m| am)?\s+(?:really\s+)?(?:like|love|into|interested in|enjoy|want(?: to)?|"
        r"think|guess)|maybe|probably|mostly|definitely)\s+",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    parts = re.split(r"\s*(?:,|;|/|\n|\band\b|&|\bplus\b|\bor\b)\s*", text, flags=re.IGNORECASE)
    out: list[str] = []
    for part in parts:
        part = part.strip(" .!?-\u2013\u2014\"'")
        part = re.sub(r"^(?:also|some|a bit of|the)\s+", "", part, flags=re.IGNORECASE)
        if not part or _nothing(part) or len(part) > 60:
            continue
        item = part[0].upper() + part[1:]
        if item.casefold() not in {o.casefold() for o in out}:
            out.append(item)
    return out[:6]


_NOTHING = re.compile(
    r"^(?:no|nope|none|nothing|not (?:yet|really|sure)|n/?a|skip|idk|i don'?t know|"
    r"not sure yet|unsure|pass|no idea|nothing yet|maybe later|later)[.!]*$",
    re.IGNORECASE,
)


def _nothing(text: str) -> bool:
    return bool(_NOTHING.match(text.strip()))


def class_year_from(text: str, today: dt.date | None = None) -> int | None:
    start = academic_start(today)
    if match := re.search(r"\b(20[2-4]\d)\b", text):
        return int(match.group(1))
    if match := re.search(r"(?:class of\s*)?'(\d\d)\b", text, re.IGNORECASE):
        return 2000 + int(match.group(1))
    low = text.casefold()
    for words, years_left in (
        (("first-year", "first year", "freshman", "1st year", "incoming"), 4),
        (("second-year", "second year", "sophomore", "2nd year"), 3),
        (("third-year", "third year", "junior", "3rd year"), 2),
        (("fourth-year", "fourth year", "senior", "4th year"), 1),
    ):
        if any(w in low for w in words):
            return start + years_left
    return None


def goal_from(text: str) -> HumanitiesGoal | None:
    low = text.casefold()
    if re.search(r"\b(deep|deeply|serious|seriously|major in|minor in|go far)\b", low):
        return "deep"
    if re.search(r"\b(enjoy|enjoying|fun|love|specific|explore|interesting)\b", low):
        return "enjoy"
    if re.search(r"\b(balance|balanced|mix|both|some of each)\b", low):
        return "balance"
    if re.search(r"\b(pass|get through|get it done|requirement|done with|check the box)\b", low):
        return "pass"
    return None


_GOAL_CHIPS = re.compile(
    r"^(?:just to pass|a balance|enjoy specific topics|to enjoy specific topics|go deep|"
    r"to go deep)\b[ .,:;-]*",
    re.IGNORECASE,
)


def workload_from(text: str) -> Workload | None:
    low = text.casefold()
    if re.search(r"\b(intense|heavy|hard|push|challenge|max)\b", low):
        return "intense"
    if re.search(r"\b(light|easy|chill|lighter|manageable|relaxed)\b", low):
        return "light"
    if re.search(r"\b(balanced|balance|medium|moderate|normal|average)\b", low):
        return "balanced"
    return None


CAREER_WORDS: dict[str, str] = {
    "phd": "Research / PhD",
    "research": "Research / PhD",
    "academ": "Research / PhD",
    "professor": "Research / PhD",
    "industry": "Industry",
    "tech": "Tech",
    "software": "Tech",
    "engineer": "Engineering",
    "startup": "Startups",
    "medic": "Medicine",
    "doctor": "Medicine",
    "med school": "Medicine",
    "law": "Law",
    "lawyer": "Law",
    "public service": "Public service",
    "government": "Public service",
    "policy": "Policy",
    "nonprofit": "Nonprofits",
    "finance": "Finance",
    "bank": "Finance",
    "consult": "Consulting",
    "teach": "Teaching",
    "journalism": "Journalism",
    "writer": "Writing",
    "art": "The arts",
}

#: Follow-ups that make a vague future domain specific (the user's example: quantum computing).
FUTURE_FOLLOWUPS: tuple[tuple[str, str, list[str]], ...] = (
    (
        "quantum",
        "Quantum computing is a wide field. Is it the physics side that draws you, the "
        "algorithms, or the hardware?",
        ["The physics", "The algorithms", "The hardware", "All of it"],
    ),
    (
        r"\bai\b|artificial intelligence|machine learning|\bml\b",
        "AI covers a lot of ground. Building the models, the mathematics underneath them, or "
        "what they do to people and society?",
        ["Building models", "The theory", "AI and society", "Not sure yet"],
    ),
    (
        "climate|environment|energy|sustainab",
        "Which side of it: the science, the policy, or the economics of it?",
        ["The science", "The policy", "The economics", "All three"],
    ),
    (
        "medic|health|biotech|neuro",
        "The lab, the clinic, or public health?",
        ["The lab", "The clinic", "Public health", "Not sure yet"],
    ),
    (
        "financ|econom|market",
        "Markets themselves, the policy that shapes them, or the mathematics behind them?",
        ["Markets", "Policy", "The mathematics", "Not sure yet"],
    ),
)


def _join(items: Sequence[str], limit: int = 3) -> str:
    items = [i for i in items if i][:limit]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


#: Words that keep their capital inside a sentence.
PROPER = frozenset(
    {
        *("greek", "roman", "latin", "english", "french", "german", "italian", "spanish"),
        *("russian", "chinese", "japanese", "korean", "arabic", "hebrew", "persian"),
        *("sanskrit", "american", "african", "european", "asian", "islamic", "jewish"),
        *("christian", "buddhist", "chicago", "uchicago", "shakespeare", "plato"),
        *("aristotle", "homer", "dante", "kant", "marx"),
    }
)


def _low(text: str) -> str:
    """An item lowercased for use inside a sentence ("Physics" -> "physics"), keeping proper
    words ("Greek tragedy") and acronyms ("AI")."""
    first = text.split(" ", 1)[0]
    if not first or first.casefold() in PROPER or (len(first) > 1 and first.isupper()):
        return text
    return text[:1].lower() + text[1:]


def _lows(items: Sequence[str], limit: int = 3) -> str:
    return _join([_low(i) for i in items], limit)


def rule_facts(topic: Topic | None, text: str, ctx: Context) -> Facts:
    """The deterministic guide's reading of one answer to a question on `topic`."""
    if not text or topic is None:
        return Facts()
    if topic == "class_year":
        return Facts(class_year=class_year_from(text))
    if topic == "interests":
        return Facts(interests=_split(text))
    if topic == "humanities":
        goal = goal_from(text)
        rest = _GOAL_CHIPS.sub("", text).strip()
        topics = [] if goal and not rest else _split(rest)
        if goal is None and topics and ctx.row.humanities_goal is None:
            goal = "enjoy"  # named topics without a goal: they want to enjoy them
        return Facts(humanities_goal=goal, humanities_topics=[t for t in topics if len(t) > 2])
    if topic == "research":
        return Facts(research_areas=_split(text))
    if topic == "career":
        low = text.casefold()
        paths = list(dict.fromkeys(v for k, v in CAREER_WORDS.items() if k in low))
        plans = None if _nothing(text) else text[:600]
        return Facts(career_plans=plans, career_paths=paths[:4])
    if topic == "future":
        last = ctx.row.future_domains[-1] if ctx.row.future_domains else None
        asked = ctx.asked("future")
        items = _split(text)
        if asked >= 2 and items and ctx.history:
            # The follow-up answer: make the last domain specific ("Quantum computing: the
            # algorithms").
            base = _previous_domain(ctx) or last
            if base:
                return Facts(future_domains=[f"{base}: {_low(items[0])}"[:60]])
        return Facts(future_domains=items)
    if topic == "constraints":
        workload = workload_from(text)
        items = [
            i
            for i in _split(text)
            if workload_from(i) is None and i.casefold() not in ("light", "balanced", "intense")
        ]
        return Facts(workload=workload, constraints=items)
    return Facts()


def _previous_domain(ctx: Context) -> str | None:
    """The domain the student named before the guide's follow-up question."""
    student = [t.text for t in ctx.history if t.role == "student"]
    for text in reversed(student):
        items = _split(text)
        if items:
            return items[0]
    return None


@dataclass(frozen=True)
class Question:
    text: str
    chips: list[str]


def question(topic: Topic, ctx: Context, patch: ProfilePatch) -> Question:
    """The deterministic guide's question on `topic`, in the student's own words where it can."""
    interests = patch.interests or list(ctx.row.interests)
    start = academic_start()
    if topic == "class_year":
        return Question(
            "Let's start simple: which class are you in? If you're still deciding, the year "
            "you started is fine too.",
            [f"Class of {start + y}" for y in (4, 3, 2, 1)] + ["Not sure yet"],
        )
    if topic == "interests":
        return Question(
            "What pulls at your attention? Name a few things you'd happily read about on a "
            "free afternoon, from physics to film to political theory.",
            ["Physics", "Computer science", "Philosophy", "Economics", "Film", "Biology"],
        )
    if topic == "humanities":
        lead = f"You mentioned {_lows(interests, 2)}. " if interests else ""
        return Question(
            lead + "Every student also takes Humanities in the Core. What do you want from it: "
            "just to pass, a balance, to enjoy specific topics, or to go deep?",
            ["Just to pass", "A balance", "Enjoy specific topics", "Go deep"],
        )
    if topic == "research":
        return Question(
            "Is there a question you'd love to work on with a professor someday? A lab, an "
            "archive, a dataset, a field site: anything counts, and 'not yet' is fine.",
            ["Not yet", "Physics lab", "Machine learning", "Cognitive science", "Archives"],
        )
    if topic == "career":
        return Question(
            "Where do you picture yourself after the College? A direction is plenty; nobody "
            "has to know yet.",
            ["Research / PhD", "Tech", "Medicine", "Law", "Public service", "Not sure yet"],
        )
    if topic == "future":
        return Question(
            "Looking further out: which fields do you want to be heading toward in ten years? "
            "Something like quantum computing, climate, or AI and society.",
            ["Quantum computing", "Climate", "AI", "Global health", "Finance", "Not sure yet"],
        )
    if topic == "constraints":
        return Question(
            "Last practical bit: how heavy do you want your quarters to feel, and is there "
            "anything to plan around, like a job, a sport, study abroad or a double major?",
            ["Light", "Balanced", "Intense", "I work part-time", "Study abroad"],
        )
    return Question("", [])


def _goal_phrase(goal: str | None, topics: Sequence[str]) -> str:
    named = _join(topics, 2)
    if goal == "pass":
        return "to get through the Humanities Core efficiently"
    if goal == "balance":
        return "a balance in the Core" + (f", with some {named}" if named else "")
    if goal == "deep":
        return "to go deep in the humanities" + (f", especially {named}" if named else "")
    if goal == "enjoy":
        return "to enjoy the humanities" + (f", above all {named}" if named else "")
    return ""


def template_portrait(ctx: Context, patch: ProfilePatch) -> Portrait:
    def get(name: str) -> Any:
        return getattr(patch, name) if name in patch.model_fields_set else getattr(ctx.row, name)

    interests = list(get("interests") or [])
    futures = list(get("future_domains") or [])
    research = list(get("research_areas") or [])
    topics = list(get("humanities_topics") or [])
    goal = get("humanities_goal")
    workload = get("workload")
    career = list(get("career_paths") or [])
    lead = interests[0] if interests else "Curious"
    if futures:
        headline = f"{lead}, heading toward {_low(futures[0])}"
    elif len(interests) > 1:
        headline = f"{lead} with a feel for {_low(interests[1])}"
    else:
        headline = f"{lead}, finding your way"
    parts = []
    if interests:
        parts.append(f"You came to UChicago for {_lows(interests)}.")
    if phrase := _goal_phrase(goal, topics):
        parts.append(f"In the Core you want {phrase}.")
    if research:
        parts.append(f"You'd like to research {_lows(research, 2)}.")
    if career:
        parts.append(f"After the College: {_lows(career, 2)}.")
    if futures:
        parts.append(f"Ten years out, {_lows(futures, 2)}.")
    if workload:
        parts.append(f"You like your quarters {workload}.")
    summary = " ".join(parts) or "You're keeping your options open, and that is a fine start."
    themes = list(dict.fromkeys([*interests[:3], *futures[:2], *research[:1]]))[:6]
    return Portrait(headline=headline[:90], summary=summary[:400], themes=themes)


def _ack(topic: Topic | None, facts: Facts, text: str) -> str:
    """A short echo of the student's last answer."""
    if not text or topic is None:
        return ""
    if _nothing(text):
        return "No problem, we can come back to that."
    if topic == "class_year" and facts.class_year:
        return f"Class of {facts.class_year}, noted."
    if topic == "interests" and facts.interests:
        return f"{_say(facts.interests)}: a good mix to build on."
    if topic == "humanities":
        if facts.humanities_topics:
            return f"{_say(facts.humanities_topics)}. I'll keep those in mind."
        if facts.humanities_goal == "pass":
            return "Fair enough: we'll keep the Core efficient."
        if facts.humanities_goal:
            return "Lovely."
    if topic == "research" and facts.research_areas:
        return f"{facts.research_areas[0]} is a good question to carry around."
    if topic == "career":
        return "Good to know where you're heading."
    if topic == "future" and facts.future_domains:
        domain = facts.future_domains[0]
        if ": " in domain:  # the answer to a follow-up ("Quantum computing: algorithms")
            return f"{domain.split(': ', 1)[1].capitalize()} it is."
        return f"{domain}, then."
    return "Got it."


def _say(items: Sequence[str], limit: int = 3) -> str:
    """Items as the start of a sentence: "Physics, film and Greek tragedy"."""
    items = [i for i in items if i][:limit]
    return _join([items[0], *(_low(i) for i in items[1:])], limit) if items else ""


TOPIC_WORDS: tuple[tuple[Topic, str], ...] = (
    ("class_year", r"class year|\bclass\b|graduat"),
    ("interests", r"interest"),
    ("humanities", r"humanit|\bcore\b"),
    ("research", r"research"),
    ("career", r"career|\bjob|after college|after the college"),
    ("future", r"future|domain|field|heading"),
    ("constraints", r"workload|constraint|\bload\b|schedule|heavy|light"),
)
#: "Update my interests", "I'd like to change my workload", "Can we revisit research?"
_CHANGE = re.compile(
    r"^\s*(?:i'?d like to |i want to |can we |could we |let'?s |please )?"
    r"(?:update|change|redo|revisit|edit|fix|talk about|go back to)\b",
    re.IGNORECASE,
)
_GO_ON = re.compile(r"^(keep going|continue|go on|next|let'?s go|sure|ok(ay)?|yes)[.!]*$", re.I)


def requested_topic(text: str, loose: bool) -> Topic | None:
    """The topic a student asks to revisit ("update my interests"); with `loose`, a bare topic
    name counts too (after the portrait, "My interests")."""
    if not (loose or _CHANGE.search(text)):
        return None
    for topic, pattern in TOPIC_WORDS:
        if re.search(pattern, text, re.IGNORECASE):
            return topic
    return None


def _ask_turn(ctx: Context, topic: Topic, lead: str, patch: ProfilePatch) -> InterviewTurnEvent:
    q = question(topic, ctx, patch)
    return InterviewTurnEvent(
        text=f"{lead} {q.text}".strip(),
        quick_replies=q.chips,
        topic=topic,
        proposed=patch,
        progress=progress_of(ctx.covered(patch), False),
        fallback=True,
    )


def rule_turn(ctx: Context) -> InterviewTurnEvent:
    """The deterministic guide (no AI): same topics, same order, simple rules."""
    if ctx.mode == "welcome_back":
        return welcome_rule_turn(ctx)
    topic_answered = ctx.answering() if ctx.mode == "reply" else None
    if ctx.mode == "reply":
        loose = topic_answered in (None, "wrapup")
        if wanted := requested_topic(ctx.message, loose):
            return _ask_turn(ctx, wanted, "Of course.", ProfilePatch())
        if _GO_ON.match(ctx.message) and loose:
            nxt = ctx.next_topic()
            if nxt != "wrapup":
                return _ask_turn(ctx, nxt, "Let's keep going.", ProfilePatch())
        if topic_answered == "wrapup" and _CHANGE.search(ctx.message):
            return InterviewTurnEvent(
                text="Of course. What would you like to change?",
                quick_replies=[
                    "My interests",
                    "The humanities",
                    "Research",
                    "Career plans",
                    "Future fields",
                    "Workload",
                ],
                topic="wrapup",
                progress=progress_of(ctx.covered(), False),
                fallback=True,
            )
    facts = rule_facts(topic_answered, ctx.message, ctx)
    patch, _ = proposed_patch(ctx, facts)
    ack = _ack(topic_answered, facts, ctx.message)

    # One follow-up to make a vague answer specific.
    follow: Question | None = None
    if topic_answered == "humanities" and ctx.asked("humanities") < 2:
        goal = patch.humanities_goal or ctx.row.humanities_goal
        topics = patch.humanities_topics or ctx.row.humanities_topics
        if goal in ("enjoy", "deep", "balance") and not topics:
            follow = Question(
                "Which topics, specifically? Greek tragedy, film, philosophy of mind, poetry, "
                "the history of science…",
                ["Greek tragedy", "Film", "Philosophy of mind", "Poetry", "Art history"],
            )
    if topic_answered == "future" and ctx.asked("future") < 2 and facts.future_domains:
        for pattern, text, chips in FUTURE_FOLLOWUPS:
            if re.search(pattern, facts.future_domains[0], re.IGNORECASE):
                follow = Question(text, chips)
                break
    if follow is not None and topic_answered is not None:
        covered = ctx.covered(patch)
        return InterviewTurnEvent(
            # A future-domain follow-up already names the domain: no echo before it.
            text=(follow.text if topic_answered == "future" else f"{ack} {follow.text}").strip(),
            quick_replies=follow.chips,
            topic=topic_answered,
            proposed=patch,
            progress=progress_of(covered, False),
            fallback=True,
        )

    nxt = ctx.next_topic(patch)
    if nxt == "wrapup":
        portrait = template_portrait(ctx, patch)
        patch = ProfilePatch.model_validate(
            {**patch.model_dump(exclude_unset=True), "portrait": portrait.model_dump()}
        )
        text = (
            f"{ack} That's everything I wanted to ask. Here's how I'd sum you up: "
            f"“{portrait.headline}.” Keep what rings true; your portrait waits on your "
            "dashboard."
        ).strip()
        return InterviewTurnEvent(
            text=text,
            quick_replies=["Change something"],
            topic="wrapup",
            proposed=patch,
            progress=1.0,
            done=True,
            fallback=True,
        )
    q = question(nxt, ctx, patch)
    if ctx.mode == "start":
        if any(sections_filled(ctx.row).values()):
            opening = f"Welcome back. Let's pick up with {TOPIC_LABELS[nxt]}."
        else:
            opening = (
                "Hi, I'm your guide. A few questions, one at a time, so your dashboard can "
                "show what you want from UChicago. Nothing is saved unless you keep it."
            )
        text = f"{opening} {q.text}"
    else:
        text = f"{ack} {q.text}".strip()
    return InterviewTurnEvent(
        text=text,
        quick_replies=q.chips,
        topic=nxt,
        proposed=patch,
        progress=progress_of(ctx.covered(patch), False),
        fallback=True,
    )


def welcome_rule_turn(ctx: Context) -> InterviewTurnEvent:
    row = ctx.row
    portrait = portrait_of(row)
    nxt = ctx.next_topic()
    bits = []
    if row.interests:
        bits.append(f"you're drawn to {_lows(row.interests, 2)}")
    if phrase := _goal_phrase(row.humanities_goal, row.humanities_topics):
        bits.append(f"that you want {phrase}")
    if row.future_domains:
        bits.append(f"that you're heading toward {_low(row.future_domains[0])}")
    memory = f"Last time you told me {_join(bits, 2)}." if bits else ""
    line = f" I still think of you as “{portrait.headline}”." if portrait.headline else ""
    if nxt != "wrapup":
        ask = f"Want to pick up with {TOPIC_LABELS[nxt]}?"
        chips = ["Keep going", "Update my interests"]
    else:
        ask = "Anything changed since then?"
        chips = ["Update my interests", "Something changed"]
    text = f"Welcome back, {ctx.username}. {memory}{line} {ask}".replace("  ", " ")
    return InterviewTurnEvent(
        text=text.strip(),
        quick_replies=chips,
        topic=nxt,
        progress=progress_of(ctx.covered(), False),
        fallback=True,
    )


# ------------------------------------------------------------------------------ the run


def _transcript(history: Sequence[InterviewTurn]) -> str:
    lines = []
    for turn in history:
        who = f"guide [{turn.topic}]" if turn.role == "guide" and turn.topic else turn.role
        lines.append(f"{who}: {turn.text}")
    return "\n".join(lines) or "(no turns yet)"


def first_message(ctx: Context) -> str:
    covered = ctx.covered()
    nxt = ctx.next_topic()
    answering = ctx.answering()
    parts = [
        f"Mode: {ctx.mode}",
        f"Today: {dt.date.today().isoformat()} (academic year {academic_start()}-"
        f"{(academic_start() + 1) % 100:02d})",
        "Topics covered: " + (", ".join(covered) or "none"),
        f"Suggested next topic: {nxt}",
    ]
    if answering and ctx.mode == "reply":
        parts.append(
            f"The newest message answers your question about: {answering} "
            f"(asked {ctx.asked(answering)} time(s) so far)"
        )
    parts += [
        "The student's profile so far:",
        untrusted("profile", json.dumps(profile_brief(ctx.row), ensure_ascii=False)),
        "The conversation so far (oldest first):",
        untrusted("conversation", _transcript(ctx.history)),
    ]
    if ctx.message:
        parts += ["The student's newest message:", untrusted("answer", ctx.message)]
    parts.append("Write your next turn with `submit_turn`.")
    return "\n".join(parts)


def _welcome_key(account: m.Account, row: m.StudentProfile) -> str:
    brief = json.dumps(profile_brief(row), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(f"{account.id}:{brief}".encode()).hexdigest()[:32]
    return f"me:welcome:{digest}"


def welcome_cached(store: Store, account: m.Account, row: m.StudentProfile) -> bool:
    """Whether a welcome-back greeting for this profile is cached (it costs no model call)."""
    return store.get(_welcome_key(account, row)) is not None


@dataclass
class InterviewRun:
    db: Session
    llm: object
    account: m.Account
    row: m.StudentProfile
    req: InterviewRequest
    store: Store
    show_unpublished: bool
    #: False when the daily limit is used up: the deterministic guide answers.
    use_ai: bool = True
    log: RunLog = field(default_factory=RunLog)

    def events(self) -> Iterator[BaseModel]:
        ctx = Context.build(self.row, self.account.username, self.req)
        cached_key = _welcome_key(self.account, self.row) if ctx.mode == "welcome_back" else None
        if cached_key is not None and (cached := self.store.get(cached_key)):
            try:
                yield InterviewTurnEvent.model_validate_json(cached)
                yield ProfileDoneEvent()
                return
            except ValidationError:
                self.store.delete(cached_key)
        turn: InterviewTurnEvent | None = None
        if self.use_ai:
            for item in self._ask_model(ctx):
                if isinstance(item, InterviewTurnEvent):
                    turn = item
                else:
                    yield item
        if turn is None:
            turn = rule_turn(ctx)
        if cached_key is not None and not turn.fallback:
            self.store.put(cached_key, turn.model_dump_json(), WELCOME_TTL_S)
        yield turn
        yield ProfileDoneEvent(fallback=turn.fallback, note=NO_AI_NOTE if turn.fallback else None)

    def _ask_model(self, ctx: Context) -> Iterator[BaseModel]:
        prompt = load_prompt(PROMPT)
        db = self.db

        def check(payload: TurnPayload) -> None:
            words = len(payload.text.split())
            if words > MAX_WORDS:
                raise ValueError(f"`text` has {words} words; keep it under 120")
            mentioned = re.findall(r"\b[A-Z]{2,5} \d{5}\b", payload.text)
            known = course_codes_in(db, payload.text)
            unknown = [c for c in mentioned if c not in known]
            if unknown:
                raise ValueError(
                    f"{', '.join(unknown)} is not a course in the catalog; mention only "
                    "courses search_courses or get_course returned"
                )

        tools = CampusTools(db, account=self.account, show_unpublished=self.show_unpublished)
        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=prompt.text,
            messages=[Message("user", first_message(ctx))],
            tools=tools.tools(TOOLS),
            submit=SubmitTool(
                "submit_turn",
                "Your next turn: the message, quick replies, its topic and the facts noted.",
                TurnPayload,
                input_schema=TURN_SCHEMA,
                check=check,
                strict=True,
            ),
            budget=BUDGET,
        )
        result: AgentResult[TurnPayload] | None = None
        try:
            for item in run_live(self.llm, spec, sink=self.log.sink, label=label):
                if isinstance(item, LiveStep):
                    yield DashboardStepEvent(tool=item.tool, label=item.label, status=item.status)
                else:
                    result = item
        except AgentError as exc:
            logger.warning("%s: no turn, the rules answered (%s)", TASK, exc.reason)
        finally:
            self._save_log()
        if result is not None:
            yield self._turn(ctx, result.output)

    def _turn(self, ctx: Context, out: TurnPayload) -> InterviewTurnEvent:
        welcome = ctx.mode == "welcome_back"
        facts = Facts() if welcome else out.facts
        portrait = out.portrait if out.topic == "wrapup" and not welcome else None
        patch, dropped = proposed_patch(ctx, facts, portrait)
        if dropped:
            logger.info("%s: dropped %d fact(s) the student did not say", TASK, dropped)
        done = bool(out.done and out.topic == "wrapup" and patch.portrait and not welcome)
        mentions = course_codes_in(self.db, out.text, limit=3)
        return InterviewTurnEvent(
            text=out.text.strip(),
            quick_replies=[q for q in out.quick_replies if q][:6],
            topic=out.topic,
            proposed=patch,
            progress=progress_of(ctx.covered(patch), done),
            done=done,
            courses=[CourseMention(code=c, title=t) for c, t in mentions.items()],
        )

    def _save_log(self) -> None:
        if not self.log.records:
            return
        run = m.AgentRun(kind="interview", plan_id=None, model="none", status="ok")
        run.created_day = dt.date.today()
        self.db.add(run)
        self.db.flush()
        self.log.save(self.db, run)
        self.db.commit()
