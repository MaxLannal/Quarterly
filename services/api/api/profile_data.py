"""The dashboard's data (`/me`): the student record (Issue #14) and the routes, read and written
for the profile router, the dashboard agent and the route drafter, plus `render_student_md()`
(what the agents read and the student exports) and `export_profile` for `/account/export`.

The student record is `student_profile` (the General Information answers) plus
`student_credit` and `student_course`. The profile row is created lazily (the first read or
write). The email is never stored here (decision 5): `ProfileOut.email` is read from
`account.email` each time, and `render_student_md()` never writes the email or the username.
Routes keep only course codes that exist in the catalog (`api.agents.live.known_courses`) and
program ids that exist.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import sqlalchemy as sa
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.agents.live import CAMPUS_YEAR, known_courses, normalize_code
from api.db import models as m
from api.profile_questions import Question, question_set
from api.schemas.profile import (
    MAX_ROUTES,
    MAX_TURNS,
    WRAPUP,
    Follows,
    InterviewMemory,
    ProfileOut,
    ProfilePatch,
    ProgramRef,
    RecordCredit,
    RouteCourse,
    RouteIn,
    RouteList,
    RouteOut,
    RoutePatch,
    TakenCourse,
    TakenCourseOut,
    TermAway,
)

#: The scalar columns a patch may set (`null` clears).
SCALAR_FIELDS = (
    "class_year",
    "expected_graduation_term",
    "entry_term",
    "entry_year_level",
    "post_grad_plan",
    "pace",
    "wants_research",
    "courses_per_term",
    "theory_vs_application",
    "working_notes",
)
#: The list columns a patch may set (`null` empties them).
LIST_FIELDS = ("intended_programs", "research_areas", "feed_categories")
#: Answers kept in their own tables.
TABLE_FIELDS = ("credits", "taken_courses")

_AWAY = TypeAdapter[list[TermAway]](list[TermAway])
QUARTER_NAMES = {"AU": "Autumn", "WI": "Winter", "SP": "Spring", "SU": "Summer"}
NOT_ANSWERED = "Not answered"


class UnknownProgramError(ValueError):
    def __init__(self, program_ids: Sequence[str]) -> None:
        super().__init__(", ".join(program_ids))
        self.program_ids = list(program_ids)


class UnknownCourseError(ValueError):
    def __init__(self, codes: Sequence[str]) -> None:
        super().__init__(", ".join(codes))
        self.codes = list(codes)


class RouteLimitError(RuntimeError):
    pass


class RouteNotFoundError(LookupError):
    pass


def today() -> dt.date:
    return dt.date.today()


# ------------------------------------------------------------------------------ profile


def find_profile(db: Session, account_id: uuid.UUID) -> m.StudentProfile | None:
    return db.get(m.StudentProfile, account_id)


def ensure_profile(db: Session, account_id: uuid.UUID) -> m.StudentProfile:
    """The account's profile, created on first use. Safe when two requests create it at once
    (the dashboard and the feed load together): the insert does nothing on a conflict."""
    row = db.get(m.StudentProfile, account_id)
    if row is None:
        db.execute(
            pg_insert(m.StudentProfile)
            .values(account_id=account_id)
            .on_conflict_do_nothing(index_elements=["account_id"])
        )
        db.flush()
        row = db.get(m.StudentProfile, account_id, populate_existing=True)
        assert row is not None
    return row


def memory_of(row: m.StudentProfile) -> InterviewMemory:
    """The dashboard agent's memory. Topics that are no longer questions (the old freeform
    interview) are dropped."""
    try:
        memory = InterviewMemory.model_validate(row.interview or {})
    except ValidationError:
        return InterviewMemory()
    known = {q.id for q in question_set().questions} | {WRAPUP}
    memory.covered = [t for t in memory.covered if t in known]
    for turn in memory.turns:
        if turn.topic is not None and turn.topic not in known:
            turn.topic = None
    return memory


def follows_of(row: m.StudentProfile) -> Follows:
    try:
        return Follows.model_validate(row.follows or {})
    except ValidationError:
        return Follows()


def terms_away_of(row: m.StudentProfile) -> list[TermAway] | None:
    if row.terms_away is None:
        return None
    try:
        return _AWAY.validate_python(row.terms_away)
    except ValidationError:
        return None


def program_refs(db: Session, ids: Iterable[str]) -> list[ProgramRef]:
    wanted = [i for i in dict.fromkeys(ids) if i]
    if not wanted:
        return []
    names = dict(
        db.execute(sa.select(m.Program.id, m.Program.name).where(m.Program.id.in_(wanted))).all()
    )
    return [ProgramRef(id=i, name=names[i]) for i in wanted if i in names]


def existing_programs(db: Session, ids: Iterable[str]) -> list[str]:
    """`ids` that are programs, in order (duplicates and unknown ids left out)."""
    return [p.id for p in program_refs(db, ids)]


# -------------------------------------------------------------- credits and taken courses


def record_credits(db: Session, account_id: uuid.UUID) -> list[RecordCredit]:
    rows = db.execute(
        sa.select(m.StudentCredit, m.Course.code)
        .outerjoin(m.Course, m.Course.id == m.StudentCredit.maps_to_course_id)
        .where(m.StudentCredit.account_id == account_id)
        .order_by(m.StudentCredit.id)
    ).all()
    return [
        RecordCredit(kind=c.kind, label=c.label, maps_to=code, units=c.units) for c, code in rows
    ]


def record_courses(db: Session, account_id: uuid.UUID) -> list[TakenCourseOut]:
    rows = db.execute(
        sa.select(m.StudentCourse, m.Course.code, m.Course.title)
        .join(m.Course, m.Course.id == m.StudentCourse.course_id)
        .where(m.StudentCourse.account_id == account_id)
        .order_by(m.StudentCourse.term_id, m.Course.code, m.StudentCourse.id)
    ).all()
    return [
        TakenCourseOut(
            course=code,
            title=title,
            term=c.term_id,
            status=c.status,
            grade=c.grade,
        )
        for c, code, title in rows
    ]


def course_ids(db: Session, codes: Iterable[str], year: str = CAMPUS_YEAR) -> dict[str, int]:
    """{code: course.id} in catalog year `year`. Raises `UnknownCourseError` for codes that are
    not courses (after normalising "cmsc14100" to "CMSC 14100")."""
    wanted: dict[str, str] = {}
    bad: list[str] = []
    for raw in codes:
        code = normalize_code(raw)
        if code is None:
            bad.append(raw)
        else:
            wanted[raw] = code
    found: dict[str, int] = {}
    if wanted:
        found = dict(
            db.execute(
                sa.select(m.Course.code, m.Course.id).where(
                    m.Course.catalog_year == year, m.Course.code.in_(set(wanted.values()))
                )
            ).all()
        )
    bad += [raw for raw, code in wanted.items() if code not in found]
    if bad:
        raise UnknownCourseError(sorted(set(bad)))
    return {raw: found[code] for raw, code in wanted.items()}


def replace_credits(
    db: Session, account_id: uuid.UUID, credits: Sequence[Any], year: str = CAMPUS_YEAR
) -> None:
    """Make the record's credits exactly `credits` (RecordCredit or planner_core Credit)."""
    ids = course_ids(db, [c.maps_to for c in credits if c.maps_to], year)
    db.execute(sa.delete(m.StudentCredit).where(m.StudentCredit.account_id == account_id))
    db.add_all(
        m.StudentCredit(
            account_id=account_id,
            kind=c.kind,
            label=c.label,
            maps_to_course_id=ids[c.maps_to] if c.maps_to else None,
            units=c.units,
        )
        for c in credits
    )


def replace_courses(
    db: Session, account_id: uuid.UUID, courses: Sequence[TakenCourse], year: str = CAMPUS_YEAR
) -> None:
    """Make the record's taken courses exactly `courses` (a course taken twice in one quarter
    is kept once)."""
    ids = course_ids(db, [c.course for c in courses], year)
    db.execute(sa.delete(m.StudentCourse).where(m.StudentCourse.account_id == account_id))
    seen: set[tuple[int, str]] = set()
    for c in courses:
        key = (ids[c.course], c.term)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            m.StudentCourse(
                account_id=account_id,
                course_id=ids[c.course],
                term_id=c.term,
                status=c.status,
                grade=c.grade,
            )
        )


# ----------------------------------------------------------------- answers and completeness


def _answer(
    row: m.StudentProfile, question: Question, credits: Sequence[Any], courses: Sequence[Any]
) -> Any:
    """The stored answer to `question` (None or an empty list when there is none; for
    `terms_away` and `class_formats` an empty list is an answer: "none")."""
    if question.field == "credits":
        return list(credits)
    if question.field == "taken_courses":
        return list(courses)
    if question.field == "terms_away":
        return terms_away_of(row)
    return getattr(row, question.field, None)


def _has_answer(question: Question, value: Any) -> bool:
    if question.field in ("terms_away", "class_formats"):
        return value is not None
    if isinstance(value, list):
        return bool(value)
    return value is not None


def applies(question: Question, row: m.StudentProfile) -> bool:
    """Whether `question` is asked of this student: its `when` fields have the given values.
    `transfer_or_later` (the registration form's checkbox) is read from the record: a student
    who started above the first year, or has credits or taken courses, checked it."""
    for name, wanted in (question.when or {}).items():
        if name == "transfer_or_later":
            continue  # the transfer questions are never required (see completeness)
        if bool(getattr(row, name, None)) is not wanted:
            return False
    return True


def answered_ids(
    row: m.StudentProfile, credits: Sequence[Any] = (), courses: Sequence[Any] = ()
) -> list[str]:
    return [
        q.id for q in question_set().questions if _has_answer(q, _answer(row, q, credits, courses))
    ]


def completeness(row: m.StudentProfile, answered: Sequence[str]) -> float:
    """Share of the questions that apply to this student and are answered. The transfer-only
    questions are left out: a first-year student has nothing to enter there."""
    wanted = [
        q.id
        for q in question_set().questions
        if not (q.when and "transfer_or_later" in q.when) and applies(q, row)
    ]
    if not wanted:
        return 0.0
    done = set(answered)
    return round(sum(1 for q in wanted if q in done) / len(wanted), 3)


def profile_out(db: Session, account: m.Account, row: m.StudentProfile) -> ProfileOut:
    credits = record_credits(db, row.account_id)
    courses = record_courses(db, row.account_id)
    answered = answered_ids(row, credits, courses)
    return ProfileOut(
        username=account.username,
        email=account.email,
        member_since=account.created_day,
        class_year=row.class_year,
        expected_graduation_term=row.expected_graduation_term,
        intended_programs=list(row.intended_programs),
        programs=program_refs(db, row.intended_programs),
        entry_term=row.entry_term,
        entry_year_level=row.entry_year_level,
        credits=credits,
        taken_courses=courses,
        post_grad_plan=row.post_grad_plan,
        pace=row.pace,
        wants_research=row.wants_research,
        research_areas=list(row.research_areas),
        courses_per_term=row.courses_per_term,
        terms_away=terms_away_of(row),
        class_formats=None if row.class_formats is None else list(row.class_formats),
        theory_vs_application=row.theory_vs_application,
        answered=answered,
        has_working_notes=bool(row.working_notes),
        feed_categories=list(row.feed_categories),
        interview=memory_of(row),
        follows=follows_of(row),
        completeness=completeness(row, answered),
        updated_day=row.updated_day,
    )


def apply_patch(db: Session, row: m.StudentProfile, patch: ProfilePatch) -> None:
    """Change only the fields the patch sets (`null` clears). Raises `UnknownProgramError` and
    `UnknownCourseError` (nothing is changed then: the caller rolls back)."""
    sent = patch.model_fields_set
    for name in SCALAR_FIELDS:
        if name in sent:
            setattr(row, name, getattr(patch, name))
    for name in LIST_FIELDS:
        if name in sent:
            value = list(getattr(patch, name) or [])
            if name == "intended_programs" and value:
                known = set(existing_programs(db, value))
                unknown = [p for p in value if p not in known]
                if unknown:
                    raise UnknownProgramError(unknown)
            setattr(row, name, value)
    if "terms_away" in sent:
        row.terms_away = (
            None if patch.terms_away is None else [t.model_dump() for t in patch.terms_away]
        )
    if "class_formats" in sent:
        row.class_formats = None if patch.class_formats is None else list(patch.class_formats)
    if "wants_research" in sent and patch.wants_research is False:
        row.research_areas = []
    if "credits" in sent:
        replace_credits(db, row.account_id, patch.credits or [])
    if "taken_courses" in sent:
        replace_courses(db, row.account_id, patch.taken_courses or [])
    if "interview" in sent:
        memory = memory_of(row)
        if patch.interview is None:
            memory = InterviewMemory()
        else:
            if patch.interview.covered is not None:
                memory.covered = patch.interview.covered
            if patch.interview.turns is not None:
                memory.turns = patch.interview.turns[-MAX_TURNS:]
        row.interview = memory.model_dump(exclude_none=True)
    if "follows" in sent:
        row.follows = (patch.follows or Follows()).model_dump()
    row.updated_day = today()


# ------------------------------------------------------------------------------ student.md


def term_label(term: str) -> str:
    """'2029-SP' -> 'Spring 2029 (2029-SP)'."""
    year, _, quarter = term.partition("-")
    name = QUARTER_NAMES.get(quarter)
    return f"{name} {year} ({term})" if name else term


def _md_text(text: str) -> str:
    """One line of the student's own words, safe inside a Markdown list item."""
    return " ".join(str(text).split()).replace("|", "/")


def _value_line(
    db: Session, question: Question, value: Any, labels: dict[str, dict[str, str]]
) -> list[str]:
    """The Markdown for one answer: one line, or a line and indented sub-items."""
    head = f"- {question.label}:"
    if not _has_answer(question, value):
        return [f"{head} {NOT_ANSWERED}"]
    field = question.field
    if field == "intended_programs":
        names = {p.id: p.name for p in program_refs(db, value)}
        return [f"{head} " + "; ".join(f"{names.get(p, p)} ({p})" for p in value)]
    if field == "credits":
        lines = [head]
        for c in value:
            kind = labels.get("kind", {}).get(c.kind, c.kind)
            parts = [f"{kind}: {_md_text(c.label)}"]
            if c.maps_to:
                parts.append(f"counts as {c.maps_to}")
            if c.units:
                parts.append(f"{c.units} units")
            lines.append("  - " + ", ".join(parts))
        return lines
    if field == "taken_courses":
        lines = [head]
        for c in value:
            status = labels.get("status", {}).get(c.status, c.status)
            title = f" {_md_text(c.title)}" if getattr(c, "title", "") else ""
            grade = f", grade {c.grade}" if c.grade else ""
            lines.append(f"  - {c.term} {c.course}{title}: {status}{grade}")
        return lines
    if field == "terms_away":
        if not value:
            return [f"{head} None"]
        away = labels.get("away", {})
        return [head] + [f"  - {term_label(t.term)}: {away.get(t.kind, t.kind)}" for t in value]
    if field == "research_areas":
        return [f"{head} " + "; ".join(_md_text(a) for a in value)]
    if field == "class_formats":
        if not value:
            return [f"{head} None"]
        return [f"{head} " + ", ".join(question.label_of(v) or v for v in value)]
    if question.value == "term":
        return [f"{head} {term_label(value)}"]
    if question.type == "scale" and question.ends:
        return [
            f"{head} {value} of {question.max} "
            f"({question.min} = {question.ends.min}, {question.max} = {question.ends.max})"
        ]
    return [f"{head} {question.label_of(value) or value}"]


def render_student_md(db: Session, row: m.StudentProfile, *, working_notes: bool = False) -> str:
    """The student record as `student.md` (Issue #14): what the agents read about the student
    and what the student exports. The General Information comes first, in the question file's
    groups and order; every unanswered question says "Not answered". `working_notes` adds the
    working information from the planner chat (the export and the planner agent ask for it).
    Never contains the email or the username."""
    qs = question_set()
    credits = record_credits(db, row.account_id)
    courses = record_courses(db, row.account_id)
    out = [
        "# Student record",
        "",
        "The student's own answers in Quarterly. The planner uses the General Information for a"
        f' first plan. "{NOT_ANSWERED}" means the student has not answered yet.',
        "",
        "## General Information",
    ]
    for group in qs.groups:
        out += ["", f"### {group.title}", ""]
        for question in qs.in_group(group.id):
            value = _answer(row, question, credits, courses)
            out += _value_line(db, question, value, qs.labels)
    if working_notes:
        out += [
            "",
            "## Working information",
            "",
            "From the planner chat. A line that applies to one plan only starts with the plan"
            " name.",
            "",
            (row.working_notes or "").strip() or "None yet.",
        ]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------------------ routes


QUARTER_ORDER = {"SU": 0, "AU": 1, "WI": 2, "SP": 3}
#: A quarter counts as "usually offered" from this predicted probability (as the catalog search).
OFFERED_MIN = 0.3


def offered_quarters(db: Session, codes: Sequence[str]) -> dict[str, list[Any]]:
    """{code: [AU, WI, SP...]}: the quarters each course is usually offered in."""
    if not codes:
        return {}
    rows = db.execute(
        sa.select(m.Course.code, m.OfferingPattern.quarter)
        .join(m.OfferingPattern, m.OfferingPattern.course_id == m.Course.id)
        .where(
            m.Course.catalog_year == CAMPUS_YEAR,
            m.Course.code.in_(list(codes)),
            m.OfferingPattern.p_offered >= OFFERED_MIN,
        )
    ).all()
    out: dict[str, list[Any]] = {}
    for code, quarter in rows:
        out.setdefault(code, []).append(quarter)
    return {c: sorted(set(q), key=lambda x: QUARTER_ORDER.get(x, 9)) for c, q in out.items()}


def clean_route(db: Session, route: RouteIn) -> RouteIn:
    """The route with unknown course codes and program ids dropped, codes normalised, each
    course once, and titles filled in from the catalog."""
    codes = [normalize_code(c.code) or "" for c in route.courses]
    titles = known_courses(db, [c for c in codes if c])
    offered = offered_quarters(db, list(titles))
    courses: list[RouteCourse] = []
    seen: set[str] = set()
    for course, code in zip(route.courses, codes, strict=True):
        if code in titles and code not in seen:
            seen.add(code)
            courses.append(
                course.model_copy(
                    update={"code": code, "title": titles[code], "offered": offered.get(code, [])}
                )
            )
    courses.sort(key=lambda c: (c.year, QUARTER_ORDER.get(c.quarter or "", 9)))
    return route.model_copy(
        update={"courses": courses, "program_ids": existing_programs(db, route.program_ids)}
    )


def _route_in(row: m.Pathway) -> RouteIn:
    try:
        return RouteIn.model_validate(
            {
                "title": row.title or "Untitled route",
                "tagline": row.tagline or "",
                "summary": row.summary or "",
                "kind": row.kind,
                "program_ids": list(row.program_ids),
                "courses": row.courses or [],
                "milestones": row.milestones or [],
                "fit": row.fit or {},
                "origin": row.origin,
            }
        )
    except ValidationError:
        return RouteIn(title=row.title[:80] or "Untitled route", origin="user")


def route_out(db: Session, row: m.Pathway) -> RouteOut:
    base = _route_in(row)
    offered = offered_quarters(db, [c.code for c in base.courses])
    base.courses = [c.model_copy(update={"offered": offered.get(c.code, [])}) for c in base.courses]
    return RouteOut(
        **base.model_dump(),
        id=row.id,
        status=row.status,
        position=row.position,
        note=row.note,
        created_day=row.created_day,
        updated_day=row.updated_day,
        programs=program_refs(db, base.program_ids),
    )


def _routes(db: Session, account_id: uuid.UUID) -> list[m.Pathway]:
    return list(
        db.scalars(
            sa.select(m.Pathway)
            .where(m.Pathway.account_id == account_id)
            .order_by(m.Pathway.position, m.Pathway.created_day, m.Pathway.id)
        )
    )


def list_routes(db: Session, account_id: uuid.UUID) -> RouteList:
    rows = _routes(db, account_id)
    chosen = next((r.id for r in rows if r.status == "chosen"), None)
    return RouteList(items=[route_out(db, r) for r in rows], chosen_id=chosen)


def create_route(db: Session, account_id: uuid.UUID, route: RouteIn) -> m.Pathway:
    """Raises `RouteLimitError` when the account already has MAX_ROUTES routes."""
    rows = _routes(db, account_id)
    if len(rows) >= MAX_ROUTES:
        raise RouteLimitError(f"at most {MAX_ROUTES} routes")
    clean = clean_route(db, route)
    row = m.Pathway(
        account_id=account_id,
        title=clean.title,
        tagline=clean.tagline or None,
        summary=clean.summary,
        kind=clean.kind,
        program_ids=clean.program_ids,
        courses=[c.model_dump() for c in clean.courses],
        milestones=[ms.model_dump() for ms in clean.milestones],
        fit=clean.fit.model_dump(),
        status="open",
        origin=clean.origin,
        position=max((r.position for r in rows), default=-1) + 1,
        created_day=today(),
        updated_day=today(),
    )
    db.add(row)
    db.flush()
    return row


def owned_route(db: Session, account_id: uuid.UUID, route_id: uuid.UUID) -> m.Pathway:
    row = db.get(m.Pathway, route_id)
    if row is None or row.account_id != account_id:
        raise RouteNotFoundError(str(route_id))
    return row


def patch_route(db: Session, row: m.Pathway, patch: RoutePatch) -> None:
    sent = patch.model_fields_set
    if "status" in sent and patch.status is not None and patch.status != row.status:
        if patch.status == "chosen":
            # One chosen route per account (index uq_pathway_one_chosen): the others go back
            # to open first, in the same transaction. Locking the account's routes first makes
            # two "choose" clicks at once wait for each other instead of failing on the index.
            mine = sa.select(m.Pathway.id).where(m.Pathway.account_id == row.account_id)
            db.execute(mine.with_for_update())
            db.execute(
                sa.update(m.Pathway)
                .where(
                    m.Pathway.account_id == row.account_id,
                    m.Pathway.status == "chosen",
                    m.Pathway.id != row.id,
                )
                .values(status="open", updated_day=today())
                .execution_options(synchronize_session="fetch")
            )
            db.flush()
        row.status = patch.status
    if "title" in sent and patch.title:
        row.title = patch.title
    if "tagline" in sent:
        row.tagline = patch.tagline or None
    if "note" in sent:
        row.note = patch.note
    if "position" in sent and patch.position is not None:
        row.position = patch.position
    row.updated_day = today()
    db.flush()


# ------------------------------------------------------------------------------ export


def export_profile(db: Session, account_id: uuid.UUID) -> dict[str, Any]:
    """The account's dashboard data for `/account/export`: the student record (without the
    email, which the export already has from the account), `student.md` with the working
    information, and every route. JSON-ready."""
    row = find_profile(db, account_id)
    if row is None and (record_credits(db, account_id) or record_courses(db, account_id)):
        # A plan save can fill the record's tables before the profile row exists.
        row = ensure_profile(db, account_id)
    profile: dict[str, Any] | None = None
    if row is not None:
        profile = {
            "class_year": row.class_year,
            "expected_graduation_term": row.expected_graduation_term,
            "intended_programs": list(row.intended_programs),
            "entry_term": row.entry_term,
            "entry_year_level": row.entry_year_level,
            "credits": [c.model_dump(mode="json") for c in record_credits(db, account_id)],
            "taken_courses": [
                c.model_dump(mode="json", exclude={"title"}) for c in record_courses(db, account_id)
            ],
            "post_grad_plan": row.post_grad_plan,
            "pace": row.pace,
            "wants_research": row.wants_research,
            "research_areas": list(row.research_areas),
            "courses_per_term": row.courses_per_term,
            "terms_away": row.terms_away,
            "class_formats": None if row.class_formats is None else list(row.class_formats),
            "theory_vs_application": row.theory_vs_application,
            "working_notes": row.working_notes,
            "feed_categories": list(row.feed_categories),
            "interview": memory_of(row).model_dump(mode="json"),
            "follows": follows_of(row).model_dump(mode="json"),
            "updates_seen": dict(row.updates_seen or {}),
            "created_day": row.created_day.isoformat(),
            "updated_day": row.updated_day.isoformat(),
            "student_md": render_student_md(db, row, working_notes=True),
        }
    routes = [
        route_out(db, r).model_dump(mode="json", exclude={"programs"})
        for r in _routes(db, account_id)
    ]
    return {"profile": profile, "routes": routes}
