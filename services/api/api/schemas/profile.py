"""The personal dashboard (`/me`): the student's profile, the interviewing guide's turns and the
routes (docs/BEST-OF-UCHICAGO-PLAN.md). The email shown on the dashboard is read from
`account.email` and never stored in `student_profile` (decision 5)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel, field_validator

from api.forum.scrub import scrub
from api.schemas.agents import ErrorEvent

HumanitiesGoal = Literal["pass", "balance", "enjoy", "deep"]
Workload = Literal["light", "balanced", "intense"]
#: The interview's topics, in the order the guide covers them.
Topic = Literal[
    "class_year",
    "interests",
    "humanities",
    "research",
    "career",
    "future",
    "constraints",
    "wrapup",
]
TOPICS: tuple[Topic, ...] = (
    "class_year",
    "interests",
    "humanities",
    "research",
    "career",
    "future",
    "constraints",
    "wrapup",
)

MAX_ITEMS = 24
MAX_ITEM_CHARS = 60
MAX_TEXT_CHARS = 1200
MAX_FEED_CATEGORIES = 16
MAX_TURNS = 24
MAX_TURN_CHARS = 2000
MAX_ROUTES = 12


def squash(text: str) -> str:
    """Whitespace collapsed, ends trimmed, emails and phone numbers scrubbed."""
    return scrub(" ".join(text.split()))


def clean_items(
    items: Iterable[str], *, max_items: int = MAX_ITEMS, max_chars: int = MAX_ITEM_CHARS
) -> list[str]:
    """Trimmed, scrubbed and deduplicated case-insensitively, in order. Raises ValueError for
    too many items or an item that is too long (empty items are dropped)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        item = squash(str(raw))
        if not item:
            continue
        if len(item) > max_chars:
            raise ValueError(f"each item has at most {max_chars} characters")
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            out.append(item)
    if len(out) > max_items:
        raise ValueError(f"at most {max_items} items")
    return out


def clean_text(text: str | None, max_chars: int = MAX_TEXT_CHARS) -> str | None:
    if text is None:
        return None
    # Paragraphs are kept; runs of spaces are not.
    lines = [" ".join(line.split()) for line in str(text).strip().splitlines()]
    out = scrub("\n".join(lines).strip())
    if len(out) > max_chars:
        raise ValueError(f"at most {max_chars} characters")
    return out or None


Items = list[Annotated[str, Field(max_length=200)]]


# ------------------------------------------------------------------------------ profile


class ProgramRef(BaseModel):
    id: str
    name: str


class Portrait(BaseModel):
    """The guide's portrait of the student, kept by the student (written by an AI)."""

    headline: str = Field(default="", max_length=90)
    summary: str = Field(default="", max_length=400)
    themes: list[str] = Field(default=[], max_length=6)

    @field_validator("headline", "summary", mode="before")
    @classmethod
    def _text(cls, value: object) -> object:
        return squash(value) if isinstance(value, str) else value

    @field_validator("themes")
    @classmethod
    def _themes(cls, value: list[str]) -> list[str]:
        return clean_items(value, max_items=6)


class InterviewTurn(BaseModel):
    role: Literal["guide", "student"]
    text: str = Field(max_length=MAX_TURN_CHARS)
    #: A guide turn's topic, so a resumed interview knows what the student was answering.
    topic: Topic | None = None


class InterviewMemory(BaseModel):
    """What the guide remembers between visits: topics covered and the last turns."""

    covered: list[Topic] = []
    turns: list[InterviewTurn] = []


class Follows(BaseModel):
    threads: list[int] = Field(default=[], max_length=500)
    courses: list[Annotated[str, Field(max_length=16)]] = Field(default=[], max_length=200)


class ProfileOut(BaseModel):
    username: str
    #: Read from the account (never copied into the profile).
    email: str
    member_since: dt.date
    class_year: int | None = None
    intended_programs: list[str] = []
    #: The intended programs with their names (programs no longer in the catalog are left out).
    programs: list[ProgramRef] = []
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
    feed_categories: list[str] = []
    portrait: Portrait = Portrait()
    interview: InterviewMemory = InterviewMemory()
    follows: Follows = Follows()
    #: Share of the main sections filled in (class year, interests, research, humanities,
    #: career, future domains, constraints or workload), 0..1.
    completeness: float = 0.0
    updated_day: dt.date


class InterviewMemoryPatch(BaseModel):
    covered: list[Topic] | None = None
    #: At most 24 are kept (the last ones); each is scrubbed.
    turns: list[InterviewTurn] | None = Field(default=None, max_length=200)

    @field_validator("covered")
    @classmethod
    def _covered(cls, value: list[Topic] | None) -> list[Topic] | None:
        return None if value is None else list(dict.fromkeys(value))

    @field_validator("turns")
    @classmethod
    def _turns(cls, value: list[InterviewTurn] | None) -> list[InterviewTurn] | None:
        if value is None:
            return None
        kept = value[-MAX_TURNS:]
        return [
            t.model_copy(update={"text": scrub(t.text.strip())}) for t in kept if t.text.strip()
        ]


class ProfilePatch(BaseModel):
    """A partial update: only the fields sent are changed (`null` clears a field). The feed,
    the Commons follow button and the companion also send these."""

    class_year: int | None = Field(default=None, ge=2020, le=2040)
    intended_programs: Items | None = None
    interests: Items | None = None
    research_areas: Items | None = None
    humanities_goal: HumanitiesGoal | None = None
    humanities_topics: Items | None = None
    humanities_note: str | None = Field(default=None, max_length=MAX_TEXT_CHARS * 2)
    career_plans: str | None = Field(default=None, max_length=MAX_TEXT_CHARS * 2)
    career_paths: Items | None = None
    future_domains: Items | None = None
    constraints: Items | None = None
    workload: Workload | None = None
    feed_categories: Items | None = None
    portrait: Portrait | None = None
    interview: InterviewMemoryPatch | None = None
    follows: Follows | None = None

    @field_validator(
        "interests",
        "research_areas",
        "humanities_topics",
        "career_paths",
        "future_domains",
        "constraints",
    )
    @classmethod
    def _items(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value)

    @field_validator("intended_programs")
    @classmethod
    def _programs(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value, max_items=8, max_chars=64)

    @field_validator("feed_categories")
    @classmethod
    def _categories(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value, max_items=MAX_FEED_CATEGORIES)

    @field_validator("humanities_note", "career_plans")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("follows")
    @classmethod
    def _follows(cls, value: Follows | None) -> Follows | None:
        if value is None:
            return None
        courses = clean_items(value.courses, max_items=200, max_chars=16)
        return Follows(threads=list(dict.fromkeys(value.threads)), courses=courses)


# ------------------------------------------------------------------------------ routes

Quarter = Literal["AU", "WI", "SP", "SU"]
CourseRole = Literal["core", "major", "minor", "elective", "humanities", "research"]
RouteKind = Literal["major", "double_major", "major_minor", "exploratory", "custom"]
RouteStatus = Literal["open", "chosen", "archived"]


class RouteCourse(BaseModel):
    code: str = Field(max_length=16)
    #: Filled in by the server from the catalog (whatever is sent is replaced).
    title: str = ""
    year: int = Field(ge=1, le=4)
    quarter: Quarter | None = None
    role: CourseRole = "elective"
    note: str = Field(default="", max_length=240)

    @field_validator("note", mode="before")
    @classmethod
    def _note(cls, value: object) -> object:
        return squash(value)[:240] if isinstance(value, str) else value


class Milestone(BaseModel):
    when: str = Field(max_length=40)
    text: str = Field(max_length=200)

    @field_validator("when", "text", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return squash(value) if isinstance(value, str) else value


class RouteFit(BaseModel):
    """How well the route fits what the student said, 0..1 (an estimate, not a grade)."""

    interests: float = Field(default=0.5, ge=0, le=1)
    career: float = Field(default=0.5, ge=0, le=1)
    humanities: float = Field(default=0.5, ge=0, le=1)
    workload: Workload | None = None


class RouteIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    tagline: str = Field(default="", max_length=140)
    summary: str = Field(default="", max_length=MAX_TEXT_CHARS)
    kind: RouteKind = "custom"
    program_ids: list[Annotated[str, Field(max_length=64)]] = Field(default=[], max_length=6)
    courses: list[RouteCourse] = Field(default=[], max_length=40)
    milestones: list[Milestone] = Field(default=[], max_length=12)
    fit: RouteFit = RouteFit()
    origin: Literal["ai", "user"] = "user"

    @field_validator("title", "tagline", mode="before")
    @classmethod
    def _line(cls, value: object) -> object:
        return squash(value) if isinstance(value, str) else value

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, value: object) -> object:
        return (clean_text(value, MAX_TEXT_CHARS * 2) or "") if isinstance(value, str) else value


class RouteOut(RouteIn):
    id: uuid.UUID
    status: RouteStatus
    position: int
    note: str | None = None
    created_day: dt.date
    updated_day: dt.date
    programs: list[ProgramRef] = []


class RouteList(BaseModel):
    items: list[RouteOut]
    #: The chosen route, if the student chose one ("keeping options open" otherwise).
    chosen_id: uuid.UUID | None = None
    max_routes: int = MAX_ROUTES


class RoutePatch(BaseModel):
    """`status: chosen` makes any other chosen route `open`; `open` on the chosen route keeps
    the options open."""

    status: RouteStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=80)
    tagline: str | None = Field(default=None, max_length=140)
    note: str | None = Field(default=None, max_length=MAX_TEXT_CHARS * 2)
    position: int | None = Field(default=None, ge=0, le=999)

    @field_validator("title", "tagline", mode="before")
    @classmethod
    def _line(cls, value: object) -> object:
        return squash(value) if isinstance(value, str) else value

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return clean_text(value)


# ------------------------------------------------------------------------------ agents


class InterviewRequest(BaseModel):
    """`start` opens (or resumes) the interview, `reply` answers the guide's last question,
    `welcome_back` greets a returning student."""

    mode: Literal["start", "reply", "welcome_back"] = "start"
    message: str | None = Field(default=None, max_length=MAX_TURN_CHARS)
    history: list[InterviewTurn] = Field(default=[], max_length=30)


class RoutesRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=4)
    #: e.g. "more humanities", "a lighter load".
    focus: str | None = Field(default=None, max_length=200)
    #: Titles of routes the student already has, so the drafts differ from them.
    keep_existing_titles: list[Annotated[str, Field(max_length=80)]] = Field(
        default=[], max_length=MAX_ROUTES
    )


class CourseMention(BaseModel):
    code: str
    title: str


class DashboardStepEvent(BaseModel):
    """The agent is calling a tool (`label` is plain English, written by the server)."""

    type: Literal["step"] = "step"
    tool: str
    label: str
    status: Literal["started", "done", "failed"]


class InterviewTurnEvent(BaseModel):
    """The guide's next message. `proposed` holds only facts the student said in this
    conversation (list fields already merged with the profile); the browser saves what the
    student keeps with PATCH /me/profile."""

    type: Literal["turn"] = "turn"
    text: str
    quick_replies: list[str] = []
    topic: Topic
    proposed: ProfilePatch = ProfilePatch()
    progress: float = 0.0
    done: bool = False
    #: Real courses the guide mentioned ({code, title}), checked against the catalog.
    courses: list[CourseMention] = []
    #: True when the deterministic guide wrote this turn (no AI).
    fallback: bool = False


class RouteDraftEvent(BaseModel):
    """One drafted route (not saved: POST /me/routes keeps it)."""

    type: Literal["route"] = "route"
    route: RouteIn
    programs: list[ProgramRef] = []
    fallback: bool = False


class ProfileDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    #: True when the answer was assembled without the AI.
    fallback: bool = False
    note: str | None = None


class InterviewEvent(
    RootModel[
        Annotated[
            DashboardStepEvent | InterviewTurnEvent | ProfileDoneEvent | ErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event `data:` payload from /agents/interview."""


class RoutesEvent(
    RootModel[
        Annotated[
            DashboardStepEvent | RouteDraftEvent | ProfileDoneEvent | ErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event `data:` payload from /agents/routes."""
