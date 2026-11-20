"""A7 the route drafter (`POST /agents/routes`, docs/BEST-OF-UCHICAGO-PLAN.md).

One run: the student's profile (as data), their optional focus ("more humanities") and the
titles of the routes they already have go to the model with the program and catalog tools; each
tool call streams as a `step`; the model ends with `submit_routes`. The server checks every
course code against the catalog again and drops the unknown ones (and unknown program ids),
fills in the course titles, and streams each route as a `route` event. Nothing is saved: the
browser keeps a draft with POST /me/routes when the student wants it.

Without a model the routes are assembled by rules from the profile: programs whose names match
the student's interests (or the ones they intend), introductory courses of the program's subject
in years 1-2 and advanced ones in years 3-4, the Core's Humanities and Social Sciences sequences
chosen by the student's humanities goal and topics, and an exploratory route. Every course comes
from the catalog, placed in the quarter it is usually offered, and the summary says the route
was assembled without the AI.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, get_args

import sqlalchemy as sa
from llm_gateway.api import AgentError, AgentResult, AgentSpec, Budget, Message, SubmitTool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from api.agents.campus_tools import CampusTools, label
from api.agents.live import CAMPUS_YEAR, LiveStep, known_courses, normalize_code, run_live
from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog
from api.agents.tools import untrusted
from api.db import models as m
from api.profile_data import clean_route, profile_brief, program_refs
from api.repo import catalog as catalog_repo
from api.schemas.catalog import ProgramSummary
from api.schemas.profile import (
    CourseRole,
    DashboardStepEvent,
    Milestone,
    ProfileDoneEvent,
    Quarter,
    RouteCourse,
    RouteDraftEvent,
    RouteFit,
    RouteIn,
    RouteKind,
    RoutesRequest,
    Workload,
)

logger = logging.getLogger("api.agents")

TASK = "a7_routes"
PROMPT = "a7_routes"
BUDGET = Budget(tool_calls=18, tokens=400_000, seconds=150)
TOOLS = ("list_programs", "get_program", "search_courses", "get_course")
#: A drafted route needs at least this many real courses (else one repair turn).
MIN_COURSES = 5

QUARTERS: tuple[str, ...] = get_args(Quarter)
ROLES: tuple[str, ...] = get_args(CourseRole)
KINDS: tuple[str, ...] = get_args(RouteKind)
WORKLOADS: tuple[str, ...] = get_args(Workload)

NO_AI = "Assembled from your profile without the AI: open each course before you rely on it."
NO_AI_NOTE = "These routes were assembled by rules from your profile, without the AI."


# ------------------------------------------------------------------------------ payload


def _clip(value: object, n: int) -> object:
    return " ".join(value.split())[:n] if isinstance(value, str) else value


class DraftCourse(BaseModel):
    code: str
    year: int = 1
    quarter: Quarter | None = None
    role: CourseRole = "elective"
    note: str = ""

    @field_validator("code", mode="before")
    @classmethod
    def _code(cls, value: object) -> object:
        return _clip(value, 16)

    @field_validator("year", mode="before")
    @classmethod
    def _year(cls, value: object) -> object:
        return min(4, max(1, int(value))) if isinstance(value, int | float) else 1

    @field_validator("quarter", mode="before")
    @classmethod
    def _quarter(cls, value: object) -> object:
        return value if value in QUARTERS else None

    @field_validator("role", mode="before")
    @classmethod
    def _role(cls, value: object) -> object:
        return value if value in ROLES else "elective"

    @field_validator("note", mode="before")
    @classmethod
    def _note(cls, value: object) -> object:
        return _clip(value, 240) if isinstance(value, str) else ""


class DraftMilestone(BaseModel):
    when: str
    text: str

    @field_validator("when", mode="before")
    @classmethod
    def _when(cls, value: object) -> object:
        return _clip(value, 40)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, value: object) -> object:
        return _clip(value, 200)


class DraftFit(BaseModel):
    interests: float = 0.5
    career: float = 0.5
    humanities: float = 0.5
    workload: Workload | None = None

    @field_validator("interests", "career", "humanities", mode="before")
    @classmethod
    def _score(cls, value: object) -> object:
        return min(1.0, max(0.0, float(value))) if isinstance(value, int | float) else 0.5

    @field_validator("workload", mode="before")
    @classmethod
    def _workload(cls, value: object) -> object:
        return value if value in WORKLOADS else None


class DraftRoute(BaseModel):
    title: str = Field(min_length=1)
    tagline: str = ""
    summary: str = ""
    kind: RouteKind = "custom"
    program_ids: list[str] = []
    courses: list[DraftCourse] = []
    milestones: list[DraftMilestone] = []
    fit: DraftFit = DraftFit()

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value: object) -> object:
        return _clip(value, 80)

    @field_validator("tagline", mode="before")
    @classmethod
    def _tagline(cls, value: object) -> object:
        return _clip(value, 140)

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, value: object) -> object:
        return _clip(value, 1200)

    @field_validator("kind", mode="before")
    @classmethod
    def _kind(cls, value: object) -> object:
        return value if value in KINDS else "custom"

    @field_validator("program_ids", mode="before")
    @classmethod
    def _programs(cls, value: object) -> object:
        return [str(v)[:64] for v in value][:6] if isinstance(value, list) else []

    @field_validator("courses", mode="before")
    @classmethod
    def _courses(cls, value: object) -> object:
        return value[:40] if isinstance(value, list) else []

    @field_validator("milestones", mode="before")
    @classmethod
    def _milestones(cls, value: object) -> object:
        return value[:12] if isinstance(value, list) else []

    def to_route(self) -> RouteIn:
        return RouteIn(
            title=self.title,
            tagline=self.tagline,
            summary=self.summary,
            kind=self.kind,
            program_ids=self.program_ids,
            courses=[
                RouteCourse(code=c.code, year=c.year, quarter=c.quarter, role=c.role, note=c.note)
                for c in self.courses
            ],
            milestones=[Milestone(when=ms.when, text=ms.text) for ms in self.milestones],
            fit=RouteFit(**self.fit.model_dump()),
            origin="ai",
        )


class RoutesPayload(BaseModel):
    routes: list[DraftRoute] = Field(min_length=1, max_length=6)


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable_enum(*values: str) -> dict[str, Any]:
    return {"anyOf": [{"type": "string", "enum": list(values)}, {"type": "null"}]}


ROUTES_SCHEMA = _obj(
    {
        "routes": {
            "type": "array",
            "items": _obj(
                {
                    "title": {"type": "string", "description": "At most 6 words."},
                    "tagline": {"type": "string", "description": "One line."},
                    "summary": {"type": "string", "description": "Two to four sentences."},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "program_ids": {"type": "array", "items": {"type": "string"}},
                    "courses": {
                        "type": "array",
                        "items": _obj(
                            {
                                "code": {"type": "string"},
                                "year": {"type": "integer", "enum": [1, 2, 3, 4]},
                                "quarter": _nullable_enum(*QUARTERS),
                                "role": {"type": "string", "enum": list(ROLES)},
                                "note": {"type": "string"},
                            }
                        ),
                    },
                    "milestones": {
                        "type": "array",
                        "items": _obj({"when": {"type": "string"}, "text": {"type": "string"}}),
                    },
                    "fit": _obj(
                        {
                            "interests": {"type": "number"},
                            "career": {"type": "number"},
                            "humanities": {"type": "number"},
                            "workload": _nullable_enum(*WORKLOADS),
                        }
                    ),
                }
            ),
        }
    }
)


# ------------------------------------------------------------------------------ the run


def first_message(row: m.StudentProfile, req: RoutesRequest, programs: list[str]) -> str:
    parts = [
        f"Draft {req.count} different route(s) for this student (catalog year {CAMPUS_YEAR}).",
        "The student's profile:",
        untrusted("profile", json.dumps(profile_brief(row), ensure_ascii=False)),
    ]
    if programs:
        parts.append("Their intended programs (ids): " + ", ".join(programs))
    if req.keep_existing_titles:
        parts += [
            "Routes they already have (make yours different):",
            untrusted("existing_routes", "\n".join(req.keep_existing_titles)),
        ]
    if req.focus and req.focus.strip():
        parts += ["What they asked for this time:", untrusted("focus", req.focus.strip())]
    parts.append("Use the tools, then call `submit_routes`.")
    return "\n".join(parts)


@dataclass
class RoutesRun:
    db: Session
    llm: object
    account: m.Account
    row: m.StudentProfile
    req: RoutesRequest
    show_unpublished: bool
    use_ai: bool = True
    log: RunLog = field(default_factory=RunLog)

    def events(self) -> Iterator[BaseModel]:
        routes: list[RouteIn] | None = None
        if self.use_ai:
            for item in self._ask_model():
                if isinstance(item, list):
                    routes = item
                else:
                    yield item
        fallback = not routes
        if not routes:
            routes = rule_routes(
                self.db,
                self.row,
                count=self.req.count,
                focus=self.req.focus,
                existing=self.req.keep_existing_titles,
                show_unpublished=self.show_unpublished,
            )
        for route in routes:
            yield RouteDraftEvent(
                route=route, programs=program_refs(self.db, route.program_ids), fallback=fallback
            )
        yield ProfileDoneEvent(fallback=fallback, note=NO_AI_NOTE if fallback else None)

    def _ask_model(self) -> Iterator[BaseModel | list[RouteIn]]:
        prompt = load_prompt(PROMPT)
        db = self.db

        def check(payload: RoutesPayload) -> None:
            codes = [c.code for r in payload.routes for c in r.courses]
            known = known_courses(db, codes)
            thin = []
            for r in payload.routes:
                real = {normalize_code(c.code) for c in r.courses} & set(known)
                if len(real) < MIN_COURSES:
                    thin.append(f"“{r.title}” has {len(real)}")
            if thin:
                unknown = sorted({c for c in codes if normalize_code(c) not in known})[:12]
                raise ValueError(
                    "every route needs at least "
                    f"{MIN_COURSES} courses from the catalog ({'; '.join(thin)}). Not in the "
                    f"catalog: {', '.join(unknown) or 'none'}. Use only codes a tool returned"
                )

        tools = CampusTools(db, account=self.account, show_unpublished=self.show_unpublished)
        spec = AgentSpec(
            task=TASK,
            prompt_version=prompt.version_tag,
            system=prompt.text,
            messages=[Message("user", first_message(self.row, self.req, self._programs()))],
            tools=tools.tools(TOOLS),
            submit=SubmitTool(
                "submit_routes",
                "Your drafted routes.",
                RoutesPayload,
                input_schema=ROUTES_SCHEMA,
                check=check,
                strict=True,
            ),
            budget=BUDGET,
        )
        result: AgentResult[RoutesPayload] | None = None
        try:
            for item in run_live(self.llm, spec, sink=self.log.sink, label=label):
                if isinstance(item, LiveStep):
                    yield DashboardStepEvent(tool=item.tool, label=item.label, status=item.status)
                else:
                    result = item
        except AgentError as exc:
            logger.info("%s: no routes (%s)", TASK, exc.reason)
        finally:
            self._save_log()
        if result is None:
            return
        routes: list[RouteIn] = []
        dropped = 0
        for draft in result.output.routes[: self.req.count]:
            route = draft.to_route()
            clean = clean_route(db, route)
            dropped += len(route.courses) - len(clean.courses)
            if clean.courses:
                routes.append(clean)
        if dropped:
            logger.warning("%s: dropped %d course(s) not in the catalog", TASK, dropped)
        yield routes

    def _programs(self) -> list[str]:
        return [p.id for p in program_refs(self.db, self.row.intended_programs)]

    def _save_log(self) -> None:
        if not self.log.records:
            return
        run = m.AgentRun(kind="routes", plan_id=None, model="none", status="ok")
        run.created_day = dt.date.today()
        self.db.add(run)
        self.db.flush()
        self.log.save(self.db, run)
        self.db.commit()


# ------------------------------------------------------------------------------ the rules

#: Topic words -> words in the title of the Humanities Core sequence about it (matched against
#: the catalog's titles, so nothing here names a course).
HUMA_HINTS: tuple[tuple[str, str], ...] = (
    (r"greek|greece|roman|rome|classic|tragedy|homer|antiq|myth", "greece"),
    (r"film|cinema|media|image|sound|music|photograph|digital", "media"),
    (r"philosoph|mind|ethic|logic|metaphysic|plato|kant", "philosoph"),
    (r"poet|poem|verse|lyric", "poetry"),
    (r"language|linguist|translation|grammar", "language"),
    (r"literat|novel|fiction|story|stories|world|reading", "literature"),
    (r"citizen|politic|justice|democra|rights", "citizen"),
    (r"travel|museum|collect|culture|exchange|art", "cultures"),
)
SOSC_HINTS: tuple[tuple[str, str], ...] = (
    (r"mind|psych|cogni|neuro|brain|behavio", "mind"),
    (r"politic|democra|government|law|policy|election", "democracy"),
    (r"global|international|world|development|migration", "global"),
    (r"religio|faith|theolog", "religion"),
    (r"power|identity|race|gender|resist|justice", "power"),
    (r"anthrop|society|self|culture|sociolog", "self"),
    (r"econom|market|finance|game theory|formal|math", "formal"),
    (r"classic|thought|theory|philosoph|marx|smith", "classics"),
)
#: Catalog titles that are never a good "key course" in a sketch.
SKIP_TITLES = re.compile(
    r"reading and research|thesis|independent study|practicum|internship|tutorial|"
    r"special topics|directed|honors paper|ba paper|research paper",
    re.IGNORECASE,
)
PROGRAM_TYPES = ("major", "minor", "specialization", "joint", "bxms")


@dataclass
class Picker:
    """Chooses real courses for the rule-built routes (each once per route)."""

    db: Session
    used: set[str] = field(default_factory=set)

    def search(
        self,
        *,
        q: str | None = None,
        subject: str | None = None,
        level: int | None = None,
        core_tag: str | None = None,
        n: int = 2,
    ) -> list[tuple[str, str]]:
        items, _ = catalog_repo.search_courses(
            self.db, CAMPUS_YEAR, q=q, subject=subject, level=level, core_tag=core_tag, limit=30
        )
        out = []
        for c in items:
            number = c.code.split(" ")[-1]
            if c.code in self.used or not number.isdigit() or not 10000 <= int(number) < 30000:
                continue
            if SKIP_TITLES.search(c.title):
                continue
            out.append((c.code, c.title))
            self.used.add(c.code)
            if len(out) >= n:
                break
        return out


def best_quarters(db: Session, codes: Sequence[str]) -> dict[str, str]:
    """The quarter each course is most often offered in (AU, WI or SP, p >= 0.3)."""
    if not codes:
        return {}
    rows = db.execute(
        sa.select(m.Course.code, m.OfferingPattern.quarter, m.OfferingPattern.p_offered)
        .join(m.OfferingPattern, m.OfferingPattern.course_id == m.Course.id)
        .where(
            m.Course.catalog_year == CAMPUS_YEAR,
            m.Course.code.in_(list(codes)),
            m.OfferingPattern.quarter.in_(("AU", "WI", "SP")),
            m.OfferingPattern.p_offered >= catalog_repo.OFFERED_MIN,
        )
    ).all()
    best: dict[str, tuple[str, float]] = {}
    for code, quarter, p in rows:
        if code not in best or p > best[code][1]:
            best[code] = (quarter, p)
    return {code: q for code, (q, _) in best.items()}


@dataclass(frozen=True)
class Sequence3:
    label: str
    courses: list[tuple[str, str]]


def core_sequences(db: Session, list_name: str, core_tag: str, title_word: str) -> list[Sequence3]:
    """The Core sequences of one area: from the catalog's course lists, else courses tagged
    with the Core area, else courses with the area in the title."""
    out: list[Sequence3] = []
    try:
        parent = catalog_repo.course_list(db, CAMPUS_YEAR, list_name)
        for name in parent.sublists:
            try:
                sub = catalog_repo.course_list(db, CAMPUS_YEAR, name)
            except catalog_repo.NotFoundError:
                continue
            titles = known_courses(db, sub.courses)
            courses = [(c, titles[c]) for c in sub.courses if c in titles]
            if courses:
                out.append(Sequence3(sub.label or name, courses[:3]))
    except catalog_repo.NotFoundError:
        pass
    if out:
        return out
    for kwargs in ({"core_tag": core_tag}, {"q": title_word}):
        items, _ = catalog_repo.search_courses(db, CAMPUS_YEAR, limit=12, **kwargs)  # type: ignore[arg-type]
        courses = [(c.code, c.title) for c in items if not SKIP_TITLES.search(c.title)]
        if courses:
            return [Sequence3(title_word, courses[i : i + 3]) for i in range(0, len(courses), 3)]
    return []


def _pick_sequence(
    seqs: list[Sequence3], hints: Sequence[tuple[str, str]], words: Sequence[str]
) -> tuple[Sequence3 | None, bool]:
    """The sequence whose titles match the student's words best; whether it matched."""
    if not seqs:
        return None, False
    text = " ".join(words).casefold()
    for pattern, fragment in hints:
        if re.search(pattern, text):
            for seq in seqs:
                if any(fragment in title.casefold() for _, title in seq.courses):
                    return seq, True
    for seq in seqs:
        titles = " ".join(t for _, t in seq.courses).casefold()
        if any(len(w) > 3 and w[:5] in titles for w in re.findall(r"[a-z]+", text)):
            return seq, True
    return seqs[0], False


def _keywords(items: Sequence[str], limit: int = 6) -> list[str]:
    out: list[str] = []
    for item in items:
        item = " ".join(item.split()).strip()
        if item and item.casefold() not in {o.casefold() for o in out}:
            out.append(item)
    return out[:limit]


def _short(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip() or name


def _subject(db: Session, program_id: str) -> str | None:
    """The course subject a program's id starts with (cmsc-bs -> CMSC), if it has courses."""
    prefix = program_id.split("-")[0].upper()
    if not re.fullmatch(r"[A-Z]{2,5}", prefix):
        return None
    exists = db.scalar(
        sa.select(sa.func.count())
        .select_from(m.Course)
        .where(m.Course.catalog_year == CAMPUS_YEAR, m.Course.subject == prefix)
    )
    return prefix if exists else None


def _score(program: ProgramSummary, words: Sequence[str]) -> int:
    """How well a program's name matches the student's words; earlier words weigh more (the
    first interest most). Words match by their first 7 letters ("physics" ~ "Physics", but
    "computing" is not "Computer")."""
    hay = f"{program.name} {program.department or ''}".casefold()
    score = 0
    for index, word in enumerate(words):
        weight = max(1, 3 - index)
        for token in re.findall(r"[a-z]{3,}", word.casefold()):
            if re.search(rf"\b{re.escape(token[:7])}", hay):
                score += weight
                break
    return score


def _join(items: Sequence[str], limit: int = 2) -> str:
    items = [i for i in items if i][:limit]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


@dataclass
class RouteBuilder:
    db: Session
    picker: Picker
    courses: list[RouteCourse] = field(default_factory=list)

    def add(self, found: list[tuple[str, str]], year: int, role: CourseRole, note: str) -> None:
        for code, title in found:
            if len(self.courses) < 18:
                self.courses.append(
                    RouteCourse(code=code, title=title, year=year, role=role, note=note[:240])
                )

    def placed(self) -> list[RouteCourse]:
        quarters = best_quarters(self.db, [c.code for c in self.courses])
        return [c.model_copy(update={"quarter": quarters.get(c.code)}) for c in self.courses]


def rule_routes(
    db: Session,
    row: m.StudentProfile,
    *,
    count: int = 3,
    focus: str | None = None,
    existing: Sequence[str] = (),
    show_unpublished: bool = False,
) -> list[RouteIn]:
    """Two to four routes assembled by rules from the profile (no AI)."""
    statuses = catalog_repo.ALL_STATUSES if show_unpublished else catalog_repo.PUBLISHED
    interests = _keywords([*row.interests, *row.future_domains])
    research = _keywords(row.research_areas, 3)
    topics = _keywords(row.humanities_topics, 4)
    goal = row.humanities_goal
    focus_text = (focus or "").casefold()
    if "humanit" in focus_text and goal in (None, "pass", "balance"):
        goal = "enjoy"
    words = [*interests, *research, *row.career_paths]

    programs = [
        p
        for p in catalog_repo.list_programs(db, CAMPUS_YEAR, statuses=statuses)
        if p.type in PROGRAM_TYPES
    ]
    intended = [p for pid in row.intended_programs for p in programs if p.id == pid]
    ranked = sorted(
        (p for p in programs if p not in intended and _score(p, words) > 0),
        key=lambda p: (-_score(p, words), p.type != "major", p.name),
    )
    candidates = [*intended, *ranked]
    primary = candidates[0] if candidates else None
    second = next(
        (
            p
            for p in candidates[1:]
            if primary is not None and p.id.split("-")[0] != primary.id.split("-")[0]
        ),
        None,
    )

    huma = core_sequences(db, "core-huma-sequences", "humanities", "Humanities")
    sosc = core_sequences(db, "core-sosc-sequences", "social_sciences", "Social Sciences")
    huma_seq, huma_matched = _pick_sequence(huma, HUMA_HINTS, topics or interests)
    sosc_seq, _ = _pick_sequence(sosc, SOSC_HINTS, [*interests, *research])

    def core(builder: RouteBuilder) -> None:
        if huma_seq is not None:
            note = f"Humanities Core: {huma_seq.label}" + (
                f", for your interest in {_join(topics or interests, 1).lower()}"
                if huma_matched
                else ""
            )
            fresh = [(c, t) for c, t in huma_seq.courses if c not in builder.picker.used]
            builder.picker.used |= {c for c, _ in fresh}
            builder.add(fresh, 1, "humanities", note)
        if goal in ("enjoy", "deep"):
            for topic in topics[:2] or interests[:1]:
                found = builder.picker.search(q=topic, core_tag=None, n=1)
                builder.add(found, 2, "humanities", f"A humanities course on {topic.lower()}")
        if sosc_seq is not None:
            fresh = [(c, t) for c, t in sosc_seq.courses if c not in builder.picker.used]
            builder.picker.used |= {c for c, _ in fresh}
            builder.add(
                fresh, 1 if goal != "deep" else 2, "core", f"Social Sciences Core: {sosc_seq.label}"
            )

    def program_courses(
        builder: RouteBuilder, program: ProgramSummary, role: CourseRole, n: int
    ) -> None:
        subject = _subject(db, program.id)
        if subject is None:
            return
        intro = builder.picker.search(subject=subject, level=10000, n=n)
        builder.add(intro[: max(1, n // 2)], 1, role, f"An early course in {_short(program.name)}")
        builder.add(intro[max(1, n // 2) :], 2, role, f"Builds your base in {_short(program.name)}")
        advanced = builder.picker.search(subject=subject, level=20000, n=n)
        builder.add(advanced[: max(1, n // 2)], 3, role, f"Advanced {_short(program.name)}")
        builder.add(advanced[max(1, n // 2) :], 4, role, f"Advanced {_short(program.name)}")

    def interest_courses(
        builder: RouteBuilder, items: Sequence[str], early: bool, late: bool
    ) -> int:
        matched = 0
        for item in items:
            got = False
            if early:
                found = builder.picker.search(q=item, level=10000, n=1)
                builder.add(found, 2, "elective", f"For your interest in {item.lower()}")
                got = got or bool(found)
            if late:
                found = builder.picker.search(q=item, level=20000, n=1)
                builder.add(
                    found, 3 if early else 4, "elective", f"Goes further into {item.lower()}"
                )
                got = got or bool(found)
            matched += int(got)
        return matched

    def research_course(builder: RouteBuilder) -> None:
        for area in research[:1]:
            found = builder.picker.search(q=area, level=20000, n=1)
            builder.add(
                found, 4, "research", f"Closest to your research interest in {area.lower()}"
            )

    def milestones(kind: RouteKind) -> list[Milestone]:
        out = [
            Milestone(
                when="Year 1, Spring", text="Meet your College adviser to talk through this route."
            )
        ]
        if kind == "exploratory":
            out.append(
                Milestone(
                    when="Year 2, Winter",
                    text="Pick the field that kept pulling at you and declare it.",
                )
            )
        else:
            out.append(
                Milestone(
                    when="Year 2, Autumn",
                    text="Declare your program once its first courses feel right.",
                )
            )
        if research:
            out.append(
                Milestone(
                    when="Year 2, Spring",
                    text=f"Ask a professor about summer research in {research[0].lower()}."[:200],
                )
            )
        if row.career_paths:
            out.append(
                Milestone(
                    when="Year 3, Summer",
                    text=f"Look for an internship toward {row.career_paths[0].lower()}."[:200],
                )
            )
        if row.future_domains:
            out.append(
                Milestone(
                    when="Year 4, Autumn",
                    text=f"Shape your last year around {row.future_domains[0].lower()}."[:200],
                )
            )
        return out[:6]

    def fit(builder: RouteBuilder, matched: int) -> RouteFit:
        total = max(1, len(interests))
        humanities = 0.6
        if goal == "pass":
            humanities = 0.8
        elif goal in ("enjoy", "deep"):
            humanities = 0.85 if huma_matched else 0.55
        return RouteFit(
            interests=round(min(1.0, 0.35 + 0.65 * matched / total), 2),
            career=0.6 if row.career_paths or row.career_plans else 0.5,
            humanities=humanities,
            workload=row.workload,
        )

    routes: list[RouteIn] = []
    goal_line = {
        "pass": "an efficient path through the Humanities Core",
        "balance": "a balanced Core",
        "enjoy": "humanities you'll enjoy" + (f", like {topics[0].lower()}" if topics else ""),
        "deep": "room to go deep in the humanities"
        + (f", especially {topics[0].lower()}" if topics else ""),
    }.get(goal or "", "the Core")

    if primary is not None:
        b = RouteBuilder(db, Picker(db))
        program_courses(b, primary, "major", 6)
        core(b)
        matched = interest_courses(b, interests[:2], early=False, late=True)
        research_course(b)
        routes.append(
            RouteIn(
                title=f"{_short(primary.name)} at the center"[:80],
                tagline=f"A {_short(primary.name)} route with {goal_line}."[:140],
                summary=(
                    f"This route puts {primary.name} first and fits your other interests around "
                    f"it. {NO_AI}"
                ),
                kind="major",
                program_ids=[primary.id],
                courses=b.placed(),
                milestones=milestones("major"),
                fit=fit(b, matched + 1),
                origin="ai",
            )
        )
    if primary is not None and second is not None:
        b = RouteBuilder(db, Picker(db))
        program_courses(b, primary, "major", 4)
        program_courses(b, second, "minor" if second.type == "minor" else "major", 4)
        core(b)
        both_major = second.type != "minor"
        routes.append(
            RouteIn(
                title=f"{_short(primary.name)} + {_short(second.name)}"[:80],
                tagline=("Two programs side by side" if both_major else "A major with a minor")
                + f", with {goal_line}."[:120],
                summary=(
                    f"This route pairs {primary.name} with {second.name}. It is the heavier "
                    f"choice: plan your electives carefully. {NO_AI}"
                ),
                kind="double_major" if both_major else "major_minor",
                program_ids=[primary.id, second.id],
                courses=b.placed(),
                milestones=milestones("double_major"),
                fit=fit(b, 2),
                origin="ai",
            )
        )
    # The exploratory route: introductory courses across the interests, the Core early, and a
    # decision at the end of year 2.
    b = RouteBuilder(db, Picker(db))
    core(b)
    matched = interest_courses(b, interests[:4] or ["Introduction"], early=True, late=True)
    research_course(b)
    routes.append(
        RouteIn(
            title="Keep your options open",
            tagline=(
                f"Two exploratory years across {_join(interests, 3).lower() or 'the College'}, "
                "then commit."
            )[:140],
            summary=(
                "This route spends the first two years sampling what interests you and the Core, "
                f"and leaves the decision for the end of the second year. {NO_AI}"
            ),
            kind="exploratory",
            program_ids=[],
            courses=b.placed(),
            milestones=milestones("exploratory"),
            fit=fit(b, matched),
            origin="ai",
        )
    )
    taken = {t.casefold() for t in existing}
    fresh = [r for r in routes if r.title.casefold() not in taken and r.courses]
    chosen = (fresh or [r for r in routes if r.courses] or routes)[: max(1, count)]
    return [clean_route(db, r) for r in chosen]
