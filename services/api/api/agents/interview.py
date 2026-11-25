"""A6 the dashboard agent (`POST /agents/interview`, Issue #16): it asks the step-2 General
Information questions of data/profile/questions.yaml, one per turn.

The server decides everything that matters: which questions are left (the first step-2 question
not yet covered whose `when` applies), what the student's newest message answers (`read_reply`,
a deterministic mapper from the reply to the question's field), the quick replies (the
question's option labels exactly as written, then "Skip") and the progress. The model only
writes the question in its own words, personal to the student's record (`student.md`), may pick
the order among the remaining questions, and maps typed answers the rules cannot read into
`facts`; the server checks those against the question (options, ranges) and the student's own
words (`proposed_patch`). Nothing is written: the browser saves what the student keeps with
PATCH /me/profile.

Without a model (not configured, failed, over budget, over the daily limit) the same questions
are asked with the file's own text and the same mapper reads the answers. The `welcome_back`
greeting is cached for a few hours per record, so returning to the dashboard does not call the
model each time.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from llm_gateway.api import AgentError, AgentResult, AgentSpec, Budget, Message, SubmitTool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from api.agents.live import COURSE_CODE, known_courses, run_live
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog
from api.agents.tools import untrusted
from api.auth.ratelimit import account_subject
from api.auth.store import Store
from api.db import models as m
from api.forum.scrub import scrub
from api.profile_data import QUARTER_NAMES, answered_ids, memory_of, render_student_md
from api.profile_data import terms_away_of as stored_terms_away
from api.profile_questions import Question, agent_questions, question_set
from api.schemas.profile import (
    MAX_ITEMS,
    MAX_TERMS_AWAY,
    WRAPUP,
    CourseMention,
    InterviewRequest,
    InterviewTurn,
    InterviewTurnEvent,
    ProfileDoneEvent,
    ProfilePatch,
    TermAway,
)

logger = logging.getLogger("api.agents")

TASK = "a6_interview"
PROMPT = "a6_interview"
#: No tools: the agent reads the student's record and words (untrusted) and holds nothing.
BUDGET = Budget(tool_calls=0, tokens=40_000, seconds=30)
HISTORY_TURNS = 16
MAX_WORDS = 100
WELCOME_TTL_S = 6 * 3600

SKIP = "Skip"
NONE_REPLY = "None"
NO_AI_NOTE = "Your guide is running without the AI right now; it asks the same questions."


# ------------------------------------------------------------------------------ questions


def question_of(topic: str | None) -> Question | None:
    """The step-2 question with this id (None for "wrapup", unknown or step-1 ids)."""
    return next((q for q in agent_questions() if q.id == topic), None)


def quick_replies(question: Question | None) -> list[str]:
    """The answers the student can tap: the option labels exactly as in the question file, in
    order (the numbers for a scale, "None" for the quarters away, nothing for a free list),
    then "Skip". The wrap-up has none."""
    if question is None:
        return []
    if question.type in ("single", "multi"):
        chips = [o.label for o in question.options]
    elif question.type == "scale" and question.min is not None and question.max is not None:
        chips = [str(n) for n in range(question.min, question.max + 1)]
    elif question.field == "terms_away":
        chips = [NONE_REPLY]
    else:
        chips = []
    return [*chips, SKIP]


def ask_text(question: Question) -> str:
    """The question as the file writes it, with its help line."""
    return f"{question.text} {question.help}" if question.help else question.text


# ------------------------------------------------------------------------------ the mapper


@dataclass(frozen=True)
class Reading:
    """What a reply says about a question: an `answer` (`value`, in the field's type), a
    `skip`, or `unclear` (ask again). `support` holds the values the student's words name
    (option values, numbers or term ids); the model's reading must agree with them."""

    kind: Literal["answer", "skip", "unclear"]
    value: Any = None
    support: tuple[Any, ...] = ()


UNCLEAR = Reading("unclear")


def _norm(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u2018", "'").casefold()
    return " ".join(text.split()).strip(' .!?,;:"')


def _find(text: str, phrase: str) -> list[re.Match[str]]:
    return list(re.finditer(rf"(?<![a-z0-9']){re.escape(phrase)}(?![a-z0-9'])", text))


_SKIP = re.compile(
    r"^(?:pass|next|later|maybe later|move on|next question|no comment|rather not say|"
    r"i'?d rather not(?: say)?|prefer not to say)$|\bskip\b"
)
_UNSURE = re.compile(
    r"^(?:not sure(?: yet)?|unsure|idk|i don'?t know(?: yet)?|dunno|no idea|no clue|maybe|"
    r"hard to say|it depends|depends)$"
)
#: Words that name each option of a single or multiple choice, besides its label and value.
SYNONYMS: dict[str, dict[Any, tuple[str, ...]]] = {
    "post_grad_plan": {
        "industry": (
            *("industry", "work", "working", "job", "a job", "company", "tech", "finance"),
            *("consulting", "startup", "business", "corporate"),
        ),
        "grad_school": (
            *("grad school", "graduate school", "grad", "phd", "ph.d", "doctorate"),
            *("masters", "master's", "academia", "professor"),
        ),
        "med_law": (
            *("med school", "medical school", "law school", "medicine", "medical", "law"),
            *("doctor", "lawyer", "md", "jd", "premed", "pre-med", "prelaw", "pre-law"),
        ),
        "undecided": (
            *("undecided", "not sure", "unsure", "don't know", "dont know", "idk"),
            *("no idea", "no clue", "not decided", "haven't decided"),
        ),
    },
    "pace": {
        "early": (
            *("early", "earlier", "fast", "faster", "quickly", "asap", "as soon as possible"),
            *("three years", "3 years", "accelerate", "ahead of time"),
        ),
        "on_time": (
            *("on time", "on-time", "four years", "4 years", "normal", "standard"),
            *("regular", "usual", "the usual"),
        ),
        "flexible": (
            *("flexible", "no rush", "doesn't matter", "don't mind", "either way"),
            *("whatever", "take my time", "slow", "slower"),
        ),
    },
    "class_formats": {
        "seminar": ("seminar", "seminars", "discussion", "discussions", "small classes"),
        "lecture": ("lecture", "lectures"),
        "lab": ("lab", "labs", "laboratory", "laboratories", "hands-on"),
        "online": ("online", "remote", "virtual"),
    },
}
_YES = re.compile(
    r"\b(?:yes|yeah|yep|yup|ya|sure|definitely|absolutely|of course|certainly|for sure|"
    r"i am|i'?m interested|i do|i would|i'?d (?:love|like) (?:to|that)|interested|very much)\b"
)
_NO = re.compile(
    r"\b(?:(?:i'?m|i am) not(?: interested| really)?|i (?:do not|don'?t)(?: think so)?|"
    r"no thanks|not (?:really|at all|interested|for me)|no|nope|nah|never|not)\b"
)
_ALL = re.compile(r"^(?:all|all of them|all of the above|any|any of them|everything|all four)$")
_NONE = re.compile(r"^(?:none|none of them|neither|nothing|no)$")
_NEGATED = re.compile(
    r"\b(?:not|no|except|without|hate|dislike|avoid|don'?t like|do not like)\s+(?:\w+\s+)?$"
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _option_value(question: Question, text: str) -> Any:
    """The option whose label (or value) the whole reply is, or None."""
    for option in question.options:
        if text in (_norm(option.label), _norm(str(option.value)).replace("_", " ")):
            return option.value
    return None


def _named_options(question: Question, text: str, *, negation: bool = False) -> list[Any]:
    """The option values the reply names (labels, values or synonyms), in option order."""
    found: list[Any] = []
    synonyms = SYNONYMS.get(question.field, {})
    for option in question.options:
        phrases = {
            _norm(option.label),
            _norm(str(option.value)).replace("_", " "),
            *synonyms.get(option.value, ()),
        }
        for phrase in phrases:
            hits = _find(text, phrase)
            if negation:
                hits = [h for h in hits if not _NEGATED.search(text[: h.start()])]
            if hits:
                found.append(option.value)
                break
    return found


def _numbers(text: str, scale_max: int | None = None) -> list[int]:
    """The whole numbers a reply names ("4", "four"), in order, each once. "7/10" and
    "7 out of 10" name only 7 when the scale ends at 10."""
    if scale_max is not None:
        text = re.sub(rf"(?:/|\bout of\b|\bof\b)\s*{scale_max}\b", " ", text)
    out: list[int] = []
    for token in re.findall(r"\b(\d{1,4}|[a-z]+)\b", text):
        value = int(token) if token.isdigit() else _NUMBER_WORDS.get(token)
        if value is not None and value not in out:
            out.append(value)
    return out


def _yes_no(text: str) -> list[bool]:
    said: list[bool] = []
    rest = text
    if _NO.search(text):
        said.append(False)
        rest = _NO.sub(" ", text)
    if _YES.search(rest):
        said.append(True)
    return said


QUARTER_WORDS = {"autumn": "AU", "fall": "AU", "winter": "WI", "spring": "SP", "summer": "SU"}
_QUARTER = re.compile(r"\b(?:autumn|fall|winter|spring|summer)\b")
_TERM_WORDS = re.compile(
    r"\b(autumn|fall|winter|spring|summer)\b(?:\s+(?:quarter|term))?(?:\s+(?:of|in))?"
    r"\s+'?(\d{4}|\d{2})\b"
)
_TERM_ID = re.compile(r"\b(20\d\d)\s*-?\s*(au|wi|sp|su)\b")
#: Words that name why a student is away, by `kind` (the labels in the file count too).
AWAY_WORDS: dict[str, tuple[str, ...]] = {
    "abroad": ("abroad", "study abroad", "exchange", "overseas"),
    "internship": ("internship", "intern", "interning", "co-op", "coop", "job", "work"),
    "leave": ("leave", "leave of absence", "time off", "gap", "break", "take off", "taking off"),
}
_STAY = re.compile(r"\b(?:none|no|nope|nah|never|stay|staying|nowhere)\b")


def _terms_in(text: str) -> list[tuple[int, str]]:
    """(position, term id) of every quarter with a year the reply names."""
    out: list[tuple[int, str]] = []
    for match in _TERM_WORDS.finditer(text):
        year = match.group(2)
        full = int(year) if len(year) == 4 else 2000 + int(year)
        out.append((match.start(), f"{full}-{QUARTER_WORDS[match.group(1)]}"))
    for match in _TERM_ID.finditer(text):
        out.append((match.start(), f"{match.group(1)}-{match.group(2).upper()}"))
    return sorted(out)


def _kinds_in(text: str) -> list[str]:
    labels = question_set().labels.get("away", {})
    found = []
    for kind, words in AWAY_WORDS.items():
        if any(_find(text, p) for p in {*words, _norm(labels.get(kind, kind))}):
            found.append(kind)
    return found


def read_terms_away(text: str) -> Reading:
    """'autumn 2027 abroad and an internship in summer 2028' -> two quarters away; 'none' (or
    'no, I'll stay') -> []. A quarter without a year, or without one reason, is unclear."""
    terms = _terms_in(text)
    support = tuple(dict.fromkeys(t for _, t in terms))
    if not terms:
        if not _QUARTER.search(text) and not _kinds_in(text) and _STAY.search(text):
            return Reading("answer", [])
        return UNCLEAR
    if len(_QUARTER.findall(text)) > len(_TERM_WORDS.findall(text)):
        return Reading("unclear", support=support)  # "autumn and winter 2027": which year?
    everywhere = _kinds_in(text)
    away: dict[str, str] = {}
    for segment in re.split(r"[,;.]|\band\b|\bthen\b|\bplus\b|\balso\b", text):
        here = [t for _, t in _terms_in(segment)]
        if not here:
            continue
        kinds = _kinds_in(segment) or (everywhere if len(everywhere) == 1 else [])
        if len(kinds) != 1:
            return Reading("unclear", support=support)
        for term in here:
            away.setdefault(term, kinds[0])
    if not away or len(away) > MAX_TERMS_AWAY:
        return Reading("unclear", support=support)
    if any(not 2020 <= int(t[:4]) <= 2040 for t in away):
        return Reading("unclear", support=support)
    return Reading("answer", [{"term": t, "kind": k} for t, k in away.items()], support)


_LEAD = re.compile(
    r"^(?:i(?:'m| am)?\s+(?:really\s+)?(?:like|love|into|interested in|enjoy|want(?: to)?|"
    r"think|guess)|(?:things|stuff|something|areas|topics) like|maybe|probably|mostly|"
    r"definitely)\s+",
    re.IGNORECASE,
)


def split_items(text: str) -> list[str]:
    """An answer cut into short items: "physics, film and Greek tragedy" -> 3 items."""
    text = _LEAD.sub("", text.strip())
    parts = re.split(r"\s*(?:,|;|/|\n|\band\b|&|\bplus\b|\bor\b)\s*", text, flags=re.IGNORECASE)
    out: list[str] = []
    for part in parts:
        part = part.strip(" .!?-\u2013\u2014\"'")
        part = re.sub(r"^(?:also|some|a bit of|the)\s+", "", part, flags=re.IGNORECASE)
        low = _norm(part)
        if not part or len(part) > 60 or _UNSURE.match(low) or _NONE.match(low):
            continue
        item = part[0].upper() + part[1:]
        if item.casefold() not in {o.casefold() for o in out}:
            out.append(item)
    return out[:6]


def read_reply(question: Question, text: str) -> Reading:
    """The deterministic reading of a reply to `question`: an exact option label (any case)
    or an obvious synonym or value; "Skip" (or "pass", "next") skips; "not sure" skips unless
    it is what an option means ("Undecided"). Integers must lie within the question's range."""
    raw = scrub(" ".join(text.split()))
    t = _norm(raw)
    if not t:
        return UNCLEAR
    if _SKIP.search(t):
        return Reading("skip")
    reading = _read(question, t, raw)
    if _UNSURE.match(t):
        named = question.type == "single" and question.value not in ("boolean", "integer")
        return reading if named and reading.kind == "answer" else Reading("skip")
    if question.type == "list" and _NONE.match(t):
        return Reading("skip")
    return reading


def _read(question: Question, t: str, raw: str) -> Reading:
    lo, hi = question.min, question.max
    exact = _option_value(question, t)
    if question.value == "boolean":
        if exact is not None:
            return Reading("answer", exact, (exact,))
        said = _yes_no(t)
        return Reading("answer", said[0], tuple(said)) if len(said) == 1 else UNCLEAR
    if question.type in ("single", "scale") and question.value == "integer":
        if exact is not None:
            return Reading("answer", exact, (exact,))
        numbers = _numbers(t, hi if question.type == "scale" else None)
        if (
            len(numbers) == 1
            and (lo is None or lo <= numbers[0])
            and (hi is None or numbers[0] <= hi)
        ):
            return Reading("answer", numbers[0], tuple(numbers))
        return Reading("unclear", support=tuple(numbers))
    if question.type == "single":
        if exact is not None:
            return Reading("answer", exact, (exact,))
        named = _named_options(question, t)
        if len(named) == 1:
            return Reading("answer", named[0], tuple(named))
        return Reading("unclear", support=tuple(named))
    if question.type == "multi":
        if exact is not None:
            return Reading("answer", [exact], (exact,))
        every = [o.value for o in question.options]
        if _ALL.match(t):
            return Reading("answer", every, tuple(every))
        if _NONE.match(t):
            return Reading("answer", [])
        named = _named_options(question, t, negation=True)
        return Reading("answer", named, tuple(named)) if named else UNCLEAR
    if question.field == "terms_away":
        return read_terms_away(t)
    if question.type == "list":
        items = split_items(raw)
        return Reading("answer", items) if items else UNCLEAR
    return UNCLEAR


# ------------------------------------------------------------------------------ grounding


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


def _merge(existing: Sequence[Any], new: Sequence[Any]) -> list[Any]:
    """`existing` plus the items of `new` it lacks (strings compared case-insensitively)."""

    def key(v: Any) -> Any:
        return v.casefold() if isinstance(v, str) else v

    merged = list(existing)
    have = {key(e) for e in existing}
    for item in new:
        if key(item) not in have and len(merged) < MAX_ITEMS:
            merged.append(item)
            have.add(key(item))
    return merged


def _says_none(text: str) -> bool:
    return bool(_NONE.match(text) or _STAY.search(text))


def proposed_patch(
    question: Question, value: Any, said: str, row: m.StudentProfile
) -> ProfilePatch | None:
    """The answer to `question` as a profile patch, or None when the value is not a valid
    answer or the student's own words (`said`) do not support it: option values must be real
    options (and among those the reply names, when it names any), integers must lie within the
    range and be a number the student wrote, every research area must share a word with the
    reply, every quarter away must be one the reply names, and "none" needs a "none" or "no".
    Research areas and class formats are merged with what the record already has."""
    support = read_reply(question, said).support
    text = _norm(said)
    out: Any
    if question.value == "boolean" or (question.type == "single" and question.value != "integer"):
        if question.label_of(value) is None or (support and value not in support):
            return None
        out = value
    elif question.value == "integer":
        lo, hi = question.min or 0, question.max or 0
        if not (isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi):
            return None
        if value not in support:
            return None
        out = value
    elif question.type == "multi":
        if not isinstance(value, list) or (not value and not _says_none(text)):
            return None
        if any(question.label_of(v) is None or (support and v not in support) for v in value):
            return None
        have = list(getattr(row, question.field) or []) if value else []
        out = _merge(have, list(dict.fromkeys(value)))
    elif question.field == "terms_away":
        if not isinstance(value, list):
            return None
        try:
            away = [TermAway.model_validate(t) for t in value]
        except ValidationError:
            return None
        if not away and (support or _QUARTER.search(text) or not _STAY.search(text)):
            return None
        for item in away:
            # A quarter the reply names; when the rules found none ("next fall abroad"), the
            # reply must at least name a quarter.
            if item.term not in support and (support or not _QUARTER.search(text)):
                return None
        out = [t.model_dump() for t in away]
    elif question.type == "list":
        if not isinstance(value, list):
            return None
        items = [i for i in (scrub(" ".join(str(v).split()))[:60] for v in value) if i]
        kept = [i for i in items if grounded(i, said)]
        if len(kept) < len(items):
            logger.info(
                "%s: dropped %d item(s) the student did not say", TASK, len(items) - len(kept)
            )
        if not kept:
            return None
        out = _merge(list(getattr(row, question.field) or []), kept)
    else:
        return None
    try:
        return ProfilePatch.model_validate({question.field: out})
    except ValidationError:
        logger.warning("%s: a proposed answer did not validate", TASK)
        return None


# ------------------------------------------------------------------------------ context


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

    def answering(self) -> Question | None:
        """The question of the guide's last turn (what the newest message answers)."""
        if self.mode != "reply":
            return None
        for turn in reversed(self.history):
            if turn.role == "guide":
                return question_of(turn.topic)
        return None

    def from_history(self) -> tuple[set[str], dict[str, Any]]:
        """The questions this conversation already moved past (answered or skipped: the
        student replied and the guide went on to another topic) and the answers the rules read
        in those replies. A guide that went on to `research_areas` heard a yes to research."""
        covered: set[str] = set()
        values: dict[str, Any] = {}
        asked: Question | None = None
        reply: str | None = None
        for turn in self.history:
            if turn.role == "student":
                if asked is not None:
                    reply = turn.text
                continue
            if asked is not None and reply is not None and turn.topic != asked.id:
                covered.add(asked.id)
                reading = read_reply(asked, reply)
                if reading.kind == "answer":
                    values[asked.field] = reading.value
                elif asked.field == "wants_research" and turn.topic == "research_areas":
                    values["wants_research"] = True
            asked, reply = question_of(turn.topic), None
        return covered, values


@dataclass
class Step:
    """The server's reading of one request: the answer to the previous question (if any) and
    what is left to ask."""

    answering: Question | None
    reading: Reading | None
    patch: ProfilePatch
    covered: set[str]
    remaining: list[Question]
    progress: float

    @property
    def retry(self) -> bool:
        return (
            self.answering is not None
            and self.reading is not None
            and (self.reading.kind == "unclear")
        )

    @property
    def answered(self) -> str | None:
        """The question whose answer `patch` holds."""
        return self.answering.id if self.answering and self.patch.model_fields_set else None

    @property
    def next_topic(self) -> str:
        return self.allowed()[0]

    def allowed(self) -> list[str]:
        """The topics the next turn may ask about: the same question again after an unclear
        reply, else any remaining question (file order first), else the wrap-up."""
        if self.retry and self.answering is not None:
            return [self.answering.id]
        return [q.id for q in self.remaining] or [WRAPUP]


def _applies(question: Question, values: dict[str, Any], row: m.StudentProfile) -> bool:
    for name, wanted in (question.when or {}).items():
        if name == "transfer_or_later":
            continue
        current = values[name] if name in values else getattr(row, name, None)
        if bool(current) is not wanted:
            return False
    return True


def settle(ctx: Context, reading: Reading | None) -> Step:
    """Turn a reading of the newest message into the proposal (through `proposed_patch`; an
    answer it refuses becomes unclear), the covered questions (the record's answers, the
    memory, this conversation), the remaining questions in file order and the progress (the
    share of the questions that apply to the student that are covered)."""
    question = ctx.answering()
    if question is None:
        reading = None
    patch = ProfilePatch()
    if question is not None and reading is not None and reading.kind == "answer":
        found = proposed_patch(question, reading.value, ctx.message, ctx.row)
        if found is None:
            reading = Reading("unclear", support=reading.support)
        else:
            patch = found
    ids = {q.id for q in agent_questions()}
    seen, values = ctx.from_history()
    covered = (set(answered_ids(ctx.row)) | set(memory_of(ctx.row).covered) | seen) & ids
    if question is not None and reading is not None and reading.kind != "unclear":
        covered.add(question.id)
    for name in patch.model_fields_set:
        values[name] = getattr(patch, name)
    applicable = [q for q in agent_questions() if _applies(q, values, ctx.row)]
    remaining = [q for q in applicable if q.id not in covered]
    done = sum(1 for q in applicable if q.id in covered)
    progress = round(done / len(applicable), 3) if applicable else 1.0
    return Step(question, reading, patch, covered, remaining, progress)


# ------------------------------------------------------------------------------ the rules


def answer_label(question: Question, value: Any) -> str:
    """An answer in words: "Graduate school", "Seminar and Lab", "Autumn 2027 (Study abroad)"."""
    if question.field == "terms_away":
        if not value:
            return NONE_REPLY
        away = question_set().labels.get("away", {})
        items = [TermAway.model_validate(t) for t in value]
        return _join([f"{_term(t.term)} ({away.get(t.kind, t.kind)})" for t in items])
    if isinstance(value, list):
        return _join([question.label_of(v) or str(v) for v in value]) or NONE_REPLY
    if question.type == "scale":
        return f"{value} of {question.max}"
    return question.label_of(value) or str(value)


def _term(term: str) -> str:
    year, _, quarter = term.partition("-")
    return f"{QUARTER_NAMES.get(quarter, quarter)} {year}"


def _join(items: Sequence[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _patch_value(patch: ProfilePatch, name: str) -> Any:
    value = getattr(patch, name)
    if name == "terms_away" and value:
        return [t.model_dump() for t in value]
    return value


def _ack(step: Step) -> str:
    """A short echo of the student's last answer."""
    if step.answering is None or step.reading is None:
        return ""
    if step.reading.kind == "skip":
        return "No problem, let's skip that one."
    if step.answered:
        value = _patch_value(step.patch, step.answering.field)
        return f"{answer_label(step.answering, value)}: noted."
    return ""


def retry_text(question: Question) -> str:
    """The brief second ask when a reply did not map to an answer."""
    lead = "Sorry, I didn't catch that."
    if question.type == "scale" and question.ends:
        return (
            f"{lead} Please give a number from {question.min} ({question.ends.min}) to "
            f"{question.max} ({question.ends.max}), or skip it."
        )
    if question.value == "integer" and question.min is not None:
        return f"{lead} {question.text} Please give a number from {question.min} to {question.max}."
    if question.type == "single":
        return f"{lead} {question.text} Please pick one of the answers below, or skip it."
    if question.type == "multi":
        labels = _join([o.label for o in question.options])
        return f"{lead} {question.text} Pick one or more of {labels}, or skip it."
    if question.field == "terms_away":
        return (
            f"{lead} Please name each quarter with its year and the reason, like “Autumn 2027, "
            "study abroad”, or answer “None”."
        )
    return f"{lead} {question.text} Name one or more, separated by commas, or skip it."


DONE_TEXT = (
    "That's all my questions. Your answers are on your dashboard, and you can change any of "
    "them there."
)


def _event(
    step: Step,
    text: str,
    topic: str,
    *,
    fallback: bool,
    courses: list[CourseMention] | None = None,
) -> InterviewTurnEvent:
    done = topic == WRAPUP
    return InterviewTurnEvent(
        text=text.strip(),
        quick_replies=quick_replies(question_of(topic)),
        topic=topic,
        answered=step.answered,
        retry=step.retry,
        proposed=step.patch,
        progress=1.0 if done else step.progress,
        done=done,
        courses=courses or [],
        fallback=fallback,
    )


def rule_turn(ctx: Context) -> InterviewTurnEvent:
    """The deterministic guide (no AI): the same questions with the file's own text, read by
    the same mapper."""
    if ctx.mode == "welcome_back":
        return welcome_rule_turn(ctx)
    question = ctx.answering()
    step = settle(ctx, read_reply(question, ctx.message) if question else None)
    if step.retry and step.answering is not None:
        return _event(step, retry_text(step.answering), step.answering.id, fallback=True)
    topic = step.next_topic
    nxt = question_of(topic)
    if ctx.mode == "start":
        if step.covered:
            lead = "Welcome back. Let's pick up where we left off."
        else:
            lead = (
                "Hi, I'm your guide. A few questions, one at a time, so your planner knows what "
                "you want. Nothing is saved unless you keep it."
            )
    else:
        lead = _ack(step) or ("Let's keep going." if nxt is not None else "")
    body = ask_text(nxt) if nxt is not None else DONE_TEXT
    return _event(step, f"{lead} {body}", topic, fallback=True)


def _recall(row: m.StudentProfile) -> str:
    """One answer from the record, so the student feels remembered."""
    for question in agent_questions():
        if question.field == "terms_away":
            away = stored_terms_away(row)
            value: Any = None if away is None else [t.model_dump() for t in away]
        else:
            value = getattr(row, question.field, None)
        if value is None or (value == [] and question.type == "list"):
            continue
        return f"Last time you told me: {question.label}, {answer_label(question, value)}."
    return ""


def welcome_rule_turn(ctx: Context) -> InterviewTurnEvent:
    step = settle(ctx, None)
    topic = step.next_topic
    nxt = question_of(topic)
    ask = f"Let's pick up where we left off. {ask_text(nxt)}" if nxt is not None else DONE_TEXT
    text = " ".join(f"Welcome back, {ctx.username}. {_recall(ctx.row)} {ask}".split())
    return _event(step, text, topic, fallback=True)


# ------------------------------------------------------------------------------ the model


class AwayFact(BaseModel):
    term: str = ""
    kind: str = ""


class Facts(BaseModel):
    """The model's reading of the student's newest message. Only the field of the question
    the message answers is used, and the server checks it, so the types are loose here."""

    post_grad_plan: str | None = None
    pace: str | None = None
    wants_research: bool | None = None
    research_areas: list[str] = []
    courses_per_term: int | None = None
    terms_away: list[AwayFact] | None = None
    class_formats: list[str] | None = None
    theory_vs_application: int | None = None


class TurnPayload(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    topic: str = Field(max_length=40)
    skipped: bool = False
    facts: Facts = Facts()


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def turn_schema() -> dict[str, Any]:
    """The `submit_turn` input; the option values come from the question file."""

    def options(qid: str) -> list[Any]:
        q = question_set().question(qid)
        return [o.value for o in q.options] if q else []

    away = question_set().question("terms_away")
    kinds = next((c.options for c in away.columns if c.id == "kind"), []) if away else []
    term = {"type": "string", "description": "A term id like 2027-AU (AU, WI, SP or SU)."}
    return _obj(
        {
            "text": {
                "type": "string",
                "description": "Your message: under 80 words, ending with exactly one question.",
            },
            "topic": {"type": "string", "enum": [*(q.id for q in agent_questions()), WRAPUP]},
            "skipped": {
                "type": "boolean",
                "description": "True only when the newest message declines to answer.",
            },
            "facts": _obj(
                {
                    "post_grad_plan": _nullable(
                        {"type": "string", "enum": options("post_grad_plan")}
                    ),
                    "pace": _nullable({"type": "string", "enum": options("pace")}),
                    "wants_research": {"type": ["boolean", "null"]},
                    "research_areas": {"type": "array", "items": {"type": "string"}},
                    "courses_per_term": {"type": ["integer", "null"]},
                    "terms_away": _nullable(
                        {
                            "type": "array",
                            "items": _obj(
                                {"term": term, "kind": {"type": "string", "enum": kinds}}
                            ),
                        }
                    ),
                    "class_formats": _nullable(
                        {
                            "type": "array",
                            "items": {"type": "string", "enum": options("class_formats")},
                        }
                    ),
                    "theory_vs_application": {"type": ["integer", "null"]},
                }
            ),
        }
    )


def model_reading(
    question: Question | None, rules: Reading | None, out: TurnPayload
) -> Reading | None:
    """The reading of the newest message with the model's help: the rules win when they read
    an answer or a skip; otherwise the model's `skipped`, or its fact for the question's field
    (which `settle` then checks with `proposed_patch`)."""
    if question is None or rules is None:
        return None
    if rules.kind != "unclear":
        return rules
    if out.skipped:
        return Reading("skip")
    value: Any = getattr(out.facts, question.field, None)
    if question.field == "terms_away" and value is not None:
        value = [t.model_dump() for t in value]
    if value is None or (value == [] and question.type == "list"):
        return rules
    return Reading("answer", value, rules.support)


def _describe(question: Question) -> str:
    line = f'- {question.id}: "{question.text}" ({question.type}'
    if question.options:
        line += "; options: " + " | ".join(o.label for o in question.options)
    if question.type == "scale" and question.ends:
        line += f"; {question.min} = {question.ends.min}, {question.max} = {question.ends.max}"
    elif question.value == "integer" and question.min is not None:
        line += f"; any whole number from {question.min} to {question.max}"
    if question.field == "terms_away":
        line += "; each quarter as a term id like 2027-AU with a reason: abroad, internship, leave"
    if question.when:
        line += "; asked only when " + ", ".join(f"{k} is {v}" for k, v in question.when.items())
    return line + ")"


def _transcript(history: Sequence[InterviewTurn]) -> str:
    lines = []
    for turn in history:
        who = f"guide [{turn.topic}]" if turn.role == "guide" and turn.topic else turn.role
        lines.append(f"{who}: {turn.text}")
    return "\n".join(lines) or "(no turns yet)"


def first_message(ctx: Context, step: Step, student_md: str) -> str:
    """The turn's data for the model: what the server read, what is left, the record and the
    conversation (the record and the student's words as untrusted data)."""
    parts = [f"Mode: {ctx.mode}", f"Today: {dt.date.today().isoformat()}"]
    question = step.answering
    if question is not None and step.reading is not None:
        parts.append(f"The newest message answers your question `{question.id}`: {question.text}")
        if step.reading.kind == "skip":
            parts.append("The server read it as: skipped. Move on to the next question.")
        elif step.answered:
            value = answer_label(question, _patch_value(step.patch, question.field))
            parts.append(
                f"The server read it as: {question.label} = {value}. Leave `facts` empty and "
                "`skipped` false."
            )
        else:
            parts.append(
                "The server could not read it. If the student's words clearly give an answer, "
                f"put it in facts.{question.field} (or set `skipped` if they decline) and ask "
                f"the next question; otherwise ask `{question.id}` again, briefly, with topic "
                f"`{question.id}`."
            )
    rest = [q for q in step.remaining if question is None or q.id != question.id]
    if rest:
        parts.append("Questions still to ask (file order; ask exactly one, `topic` is its id):")
        parts += [_describe(q) for q in rest]
    else:
        parts.append("No questions are left after this one: write the wrap-up (topic `wrapup`).")
    parts += [
        "The student's record:",
        untrusted("student_md", student_md),
        "The conversation so far (oldest first):",
        untrusted("conversation", _transcript(ctx.history)),
    ]
    if ctx.message:
        parts += ["The student's newest message:", untrusted("answer", ctx.message)]
    parts.append("Write your next turn with `submit_turn`.")
    return "\n".join(parts)


def _codes(text: str) -> list[str]:
    return list(dict.fromkeys(f"{a} {b}" for a, b in COURSE_CODE.findall(text.upper())))


# ------------------------------------------------------------------------------ the run


def welcome_key(account_id: uuid.UUID) -> str:
    """One cached greeting per account, so deleting the account can delete it too (it restates
    the student's answers). The value holds the record's digest with the turn."""
    return f"me:welcome:{account_subject(account_id)}"


def _welcome_digest(account: m.Account, row: m.StudentProfile) -> str:
    """Changes whenever an answer or the covered questions change."""
    answers: dict[str, Any] = {
        q.field: getattr(row, q.field, None)
        for q in question_set().questions
        if q.field not in ("credits", "taken_courses")
    }
    answers["covered"] = memory_of(row).covered
    blob = json.dumps(answers, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{account.id}:{blob}".encode()).hexdigest()[:32]


def _cached_welcome(store: Store, account: m.Account, row: m.StudentProfile) -> str | None:
    """The cached greeting's JSON when it was made for this state of the record."""
    raw = store.get(welcome_key(account.id))
    if raw is None:
        return None
    try:
        cached = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(cached, dict) or cached.get("digest") != _welcome_digest(account, row):
        return None
    turn = cached.get("turn")
    return turn if isinstance(turn, str) else None


def welcome_cached(store: Store, account: m.Account, row: m.StudentProfile) -> bool:
    """Whether a welcome-back greeting for this record is cached (it costs no model call)."""
    return _cached_welcome(store, account, row) is not None


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
        welcome = ctx.mode == "welcome_back"
        if welcome and (cached := _cached_welcome(self.store, self.account, self.row)):
            try:
                yield InterviewTurnEvent.model_validate_json(cached)
                yield ProfileDoneEvent()
                return
            except ValidationError:
                self.store.delete(welcome_key(self.account.id))
        turn = self._ask_model(ctx) if self.use_ai else None
        if turn is None:
            turn = rule_turn(ctx)
        if welcome and not turn.fallback:
            value = {
                "digest": _welcome_digest(self.account, self.row),
                "turn": turn.model_dump_json(),
            }
            self.store.put(welcome_key(self.account.id), json.dumps(value), WELCOME_TTL_S)
        yield turn
        yield ProfileDoneEvent(fallback=turn.fallback, note=NO_AI_NOTE if turn.fallback else None)

    def _ask_model(self, ctx: Context) -> InterviewTurnEvent | None:
        question = ctx.answering()
        rules = read_reply(question, ctx.message) if question is not None else None
        # No grades: the questions do not need them, and this goes to the AI provider (M21-1).
        student_md = render_student_md(self.db, self.row, grades=False)
        record_codes = set(_codes(student_md))
        prompt = load_prompt(PROMPT)

        def check(payload: TurnPayload) -> None:
            words = len(payload.text.split())
            if words > MAX_WORDS:
                raise ValueError(f"`text` has {words} words; keep it under 80")
            if set(_codes(payload.text)) - record_codes:
                raise ValueError("do not name courses: this conversation is only the questions")
            step = settle(ctx, model_reading(question, rules, payload))
            allowed = step.allowed()
            if payload.topic in allowed:
                return
            if step.retry and question is not None:
                raise ValueError(
                    f"the newest message gives no valid {question.field} the student's words "
                    f"support (see the options and range): either put one in "
                    f"facts.{question.field}, or ask `{question.id}` again with topic "
                    f"`{question.id}`"
                )
            raise ValueError(f"`topic` must be one of: {', '.join(allowed)}")

        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=prompt.text,
            messages=[Message("user", first_message(ctx, settle(ctx, rules), student_md))],
            tools=[],
            submit=SubmitTool(
                "submit_turn",
                "Your next turn: the message, the question it asks and the answer you read.",
                TurnPayload,
                input_schema=turn_schema(),
                check=check,
                strict=True,
            ),
            budget=BUDGET,
        )
        result: AgentResult[TurnPayload] | None = None
        try:
            for item in run_live(self.llm, spec, sink=self.log.sink):
                if isinstance(item, AgentResult):
                    result = item
        except AgentError as exc:
            logger.warning("%s: no turn, the rules answered (%s)", TASK, exc.reason)
        except Exception as exc:  # any other failure: the rules answer, the stream goes on
            logger.warning("%s: no turn, the rules answered (%s)", TASK, type(exc).__name__)
        finally:
            self._save_log()
        if result is None:
            return None
        out = result.output
        step = settle(ctx, model_reading(question, rules, out))
        if out.topic not in step.allowed():  # check() refused this already
            return None
        mentions = known_courses(self.db, _codes(out.text))
        courses = [CourseMention(code=c, title=t) for c, t in mentions.items()][:3]
        return _event(step, out.text, out.topic, fallback=False, courses=courses)

    def _save_log(self) -> None:
        if not self.log.records:
            return
        run = m.AgentRun(kind="interview", plan_id=None, model="none", status="ok")
        run.created_day = dt.date.today()
        self.db.add(run)
        self.db.flush()
        self.log.save(self.db, run)
        self.db.commit()
