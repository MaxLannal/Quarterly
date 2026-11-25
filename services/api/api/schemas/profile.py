"""The personal dashboard (`/me`): the student record (Issue #14), the dashboard agent's turns
(Issue #16) and the routes. The email shown on the dashboard is read from `account.email` and
never stored in `student_profile` (decision 5)."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable
from typing import Annotated, Literal

from planner_core.models import Grading
from pydantic import BaseModel, Field, RootModel, field_validator

from api.forum.scrub import scrub
from api.schemas.agents import ErrorEvent

PostGradPlan = Literal["industry", "grad_school", "med_law", "undecided"]
Pace = Literal["early", "on_time", "flexible"]
ClassFormat = Literal["seminar", "lecture", "lab", "online"]
AwayKind = Literal["abroad", "internship", "leave"]
CreditKind = Literal["AP", "placement", "transfer"]
TakenStatus = Literal["completed", "in_progress"]
#: A term id (`2026-AU`; planner_core.terms).
TermId = Annotated[str, Field(pattern=r"^\d{4}-(AU|WI|SP|SU)$")]
#: The dashboard agent's topics are the ids of the step-2 questions in
#: data/profile/questions.yaml, then "wrapup".
Topic = Annotated[str, Field(max_length=40, pattern=r"^[a-z_]+$")]
WRAPUP = "wrapup"

MAX_ITEMS = 24
MAX_ITEM_CHARS = 60
MAX_TEXT_CHARS = 1200
MAX_FEED_CATEGORIES = 16
MAX_TURNS = 24
MAX_TURN_CHARS = 2000
MAX_ROUTES = 12
MAX_CREDITS = 40
MAX_TAKEN = 80
MAX_TERMS_AWAY = 12
MAX_WORKING_NOTES_CHARS = 20_000


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


class TermAway(BaseModel):
    """A quarter the student plans to spend away."""

    term: TermId
    kind: AwayKind


class RecordCredit(BaseModel):
    """An AP, placement or transfer credit (planner_core `Credit`)."""

    kind: CreditKind
    label: str = Field(min_length=1, max_length=120)
    #: The course code it counts as, if any (checked against the catalog).
    maps_to: str | None = Field(default=None, max_length=16)
    units: int = Field(default=0, ge=0, le=1000)

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, value: object) -> object:
        return squash(value) if isinstance(value, str) else value


class TakenCourse(BaseModel):
    """A UChicago course the student took or is taking. `grading`, `units` and `locked` are the
    plan item's (planner_core `PlanItem`): a rule that needs a letter grade does not count a
    Pass/Fail course, so every editor sends them back unchanged."""

    course: str = Field(min_length=1, max_length=16)
    term: TermId
    status: TakenStatus = "completed"
    grade: str | None = Field(default=None, max_length=4)
    grading: Grading = "letter"
    #: Overrides the catalog units (variable-unit courses); None = the catalog's.
    units: int | None = Field(default=None, ge=0)
    #: Locked in the planner (it cannot be dragged or removed there).
    locked: bool = False


class TakenCourseOut(TakenCourse):
    #: The course title, filled in by the server from the catalog.
    title: str = ""


class InterviewTurn(BaseModel):
    role: Literal["guide", "student"]
    text: str = Field(max_length=MAX_TURN_CHARS)
    #: A guide turn's topic (a question id), so a resumed conversation knows what the student
    #: was answering.
    topic: Topic | None = None


class InterviewMemory(BaseModel):
    """What the dashboard agent remembers between visits: the questions it covered (answered
    or skipped) and the last turns."""

    covered: list[Topic] = []
    turns: list[InterviewTurn] = []


class Follows(BaseModel):
    threads: list[int] = Field(default=[], max_length=500)
    courses: list[Annotated[str, Field(max_length=16)]] = Field(default=[], max_length=200)


class ProfileOut(BaseModel):
    """The student record (Issue #14) as the dashboard shows it. `null` = not answered."""

    username: str
    #: Read from the account (never copied into the student record).
    email: str
    member_since: dt.date
    # Academic background.
    class_year: int | None = None
    expected_graduation_term: str | None = None
    intended_programs: list[str] = []
    #: The intended programs with their names (programs no longer in the catalog are left out).
    programs: list[ProgramRef] = []
    entry_term: str | None = None
    entry_year_level: int | None = None
    credits: list[RecordCredit] = []
    taken_courses: list[TakenCourseOut] = []
    # Goals.
    post_grad_plan: PostGradPlan | None = None
    pace: Pace | None = None
    wants_research: bool | None = None
    research_areas: list[str] = []
    # Scheduling.
    courses_per_term: int | None = None
    terms_away: list[TermAway] | None = None
    # Learning preferences.
    class_formats: list[ClassFormat] | None = None
    theory_vs_application: int | None = None
    #: The ids of the General Information questions that have an answer.
    answered: list[str] = []
    #: True when the planner chat left working information (Issue #17).
    has_working_notes: bool = False
    feed_categories: list[str] = []
    interview: InterviewMemory = InterviewMemory()
    follows: Follows = Follows()
    #: Share of the General Information questions answered (the transfer-only questions are
    #: left out), 0..1.
    completeness: float = 0.0
    updated_day: dt.date


class InterviewMemoryPatch(BaseModel):
    covered: list[Topic] | None = None
    #: At most 24 are kept (the last ones); each is scrubbed.
    turns: list[InterviewTurn] | None = Field(default=None, max_length=200)

    @field_validator("covered")
    @classmethod
    def _covered(cls, value: list[str] | None) -> list[str] | None:
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
    """A partial update: only the fields sent are changed (`null` clears a field). `credits`
    and `taken_courses` replace the whole list. The registration form, the dashboard, the
    dashboard agent's accepted answers, the feed and the Commons follow button send these."""

    class_year: int | None = Field(default=None, ge=2020, le=2040)
    expected_graduation_term: TermId | None = None
    intended_programs: Items | None = None
    entry_term: TermId | None = None
    entry_year_level: int | None = Field(default=None, ge=1, le=4)
    credits: list[RecordCredit] | None = Field(default=None, max_length=MAX_CREDITS)
    taken_courses: list[TakenCourse] | None = Field(default=None, max_length=MAX_TAKEN)
    post_grad_plan: PostGradPlan | None = None
    pace: Pace | None = None
    wants_research: bool | None = None
    research_areas: Items | None = None
    courses_per_term: int | None = Field(default=None, ge=1, le=6)
    terms_away: list[TermAway] | None = Field(default=None, max_length=MAX_TERMS_AWAY)
    class_formats: list[ClassFormat] | None = Field(default=None, max_length=4)
    theory_vs_application: int | None = Field(default=None, ge=1, le=10)
    #: The planner chat's working information (Markdown); `null` deletes it.
    working_notes: str | None = Field(default=None, max_length=MAX_WORKING_NOTES_CHARS)
    feed_categories: Items | None = None
    interview: InterviewMemoryPatch | None = None
    follows: Follows | None = None

    @field_validator("research_areas")
    @classmethod
    def _items(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value)

    @field_validator("intended_programs")
    @classmethod
    def _programs(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value, max_items=8, max_chars=64)

    @field_validator("class_formats")
    @classmethod
    def _formats(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else list(dict.fromkeys(value))

    @field_validator("terms_away")
    @classmethod
    def _away(cls, value: list[TermAway] | None) -> list[TermAway] | None:
        if value is None:
            return None
        seen: dict[str, TermAway] = {}
        for item in value:
            seen.setdefault(item.term, item)
        return list(seen.values())

    @field_validator("feed_categories")
    @classmethod
    def _categories(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_items(value, max_items=MAX_FEED_CATEGORIES)

    @field_validator("working_notes")
    @classmethod
    def _notes(cls, value: str | None) -> str | None:
        return clean_text(value, MAX_WORKING_NOTES_CHARS)

    @field_validator("follows")
    @classmethod
    def _follows(cls, value: Follows | None) -> Follows | None:
        if value is None:
            return None
        courses = clean_items(value.courses, max_items=200, max_chars=16)
        return Follows(threads=list(dict.fromkeys(value.threads)), courses=courses)


# ------------------------------------------------------------------------------ routes

Quarter = Literal["AU", "WI", "SP", "SU"]
#: A route's estimated load (routes only; the student record has `courses_per_term`).
Workload = Literal["light", "balanced", "intense"]
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
    #: The quarters the course is usually offered in (AU, WI, SP), filled by the server from
    #: the catalog's offering patterns (whatever is sent is replaced).
    offered: list[Quarter] = []

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
    """The dashboard agent's next message (Issue #16). `topic` is the id of the question it
    asks (data/profile/questions.yaml) or "wrapup". `quick_replies` are that question's option
    labels, unchanged, then "Skip". `proposed` holds only the answer the student gave to the
    previous question, mapped to its field (list fields already merged with the record); the
    browser saves it with PATCH /me/profile once the student accepts it."""

    type: Literal["turn"] = "turn"
    text: str
    quick_replies: list[str] = []
    topic: Topic
    #: The question whose answer `proposed` holds (None when the turn proposes nothing).
    answered: Topic | None = None
    #: True when the student's last message did not map to an answer and the question is
    #: asked again.
    retry: bool = False
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
