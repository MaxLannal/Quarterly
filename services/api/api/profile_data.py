"""The dashboard's data (`/me`): the student profile and the routes, read and written for the
profile router, the interviewing guide and the route drafter, plus `export_profile` for
`/account/export`.

The profile row is created lazily (the first read or write). The email is never stored here
(decision 5): `ProfileOut.email` is read from `account.email` each time. Routes keep only course
codes that exist in the catalog (`api.agents.live.known_courses`) and program ids that exist.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.orm import Session

from api.agents.live import known_courses, normalize_code
from api.db import models as m
from api.schemas.profile import (
    MAX_ROUTES,
    MAX_TURNS,
    Follows,
    InterviewMemory,
    Portrait,
    ProfileOut,
    ProfilePatch,
    ProgramRef,
    RouteCourse,
    RouteIn,
    RouteList,
    RouteOut,
    RoutePatch,
)

#: The list columns a patch may set.
LIST_FIELDS = (
    "intended_programs",
    "interests",
    "research_areas",
    "humanities_topics",
    "career_paths",
    "future_domains",
    "constraints",
    "feed_categories",
)
SCALAR_FIELDS = ("class_year", "humanities_goal", "humanities_note", "career_plans", "workload")


class UnknownProgramError(ValueError):
    def __init__(self, program_ids: Sequence[str]) -> None:
        super().__init__(", ".join(program_ids))
        self.program_ids = list(program_ids)


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
    """The account's profile, created (and flushed) on first use."""
    row = db.get(m.StudentProfile, account_id)
    if row is None:
        row = m.StudentProfile(
            account_id=account_id,
            intended_programs=[],
            interests=[],
            research_areas=[],
            humanities_topics=[],
            career_paths=[],
            future_domains=[],
            constraints=[],
            feed_categories=[],
            portrait={},
            interview={},
            follows={},
            updates_seen={},
            created_day=today(),
            updated_day=today(),
        )
        db.add(row)
        db.flush()
    return row


def portrait_of(row: m.StudentProfile) -> Portrait:
    try:
        return Portrait.model_validate(row.portrait or {})
    except ValidationError:
        return Portrait()


def memory_of(row: m.StudentProfile) -> InterviewMemory:
    try:
        return InterviewMemory.model_validate(row.interview or {})
    except ValidationError:
        return InterviewMemory()


def follows_of(row: m.StudentProfile) -> Follows:
    try:
        return Follows.model_validate(row.follows or {})
    except ValidationError:
        return Follows()


def sections_filled(row: m.StudentProfile | ProfileOut) -> dict[str, bool]:
    """The main sections of the portrait and whether each has something in it."""
    return {
        "class_year": row.class_year is not None,
        "interests": bool(row.interests),
        "research": bool(row.research_areas),
        "humanities": row.humanities_goal is not None or bool(row.humanities_topics),
        "career": bool(row.career_plans) or bool(row.career_paths),
        "future": bool(row.future_domains),
        "constraints": bool(row.constraints) or row.workload is not None,
    }


def completeness(row: m.StudentProfile | ProfileOut) -> float:
    filled = sections_filled(row)
    return round(sum(filled.values()) / len(filled), 3)


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


def profile_out(db: Session, account: m.Account, row: m.StudentProfile) -> ProfileOut:
    out = ProfileOut(
        username=account.username,
        email=account.email,
        member_since=account.created_day,
        class_year=row.class_year,
        intended_programs=list(row.intended_programs),
        programs=program_refs(db, row.intended_programs),
        interests=list(row.interests),
        research_areas=list(row.research_areas),
        humanities_goal=row.humanities_goal,
        humanities_topics=list(row.humanities_topics),
        humanities_note=row.humanities_note,
        career_plans=row.career_plans,
        career_paths=list(row.career_paths),
        future_domains=list(row.future_domains),
        constraints=list(row.constraints),
        workload=row.workload,
        feed_categories=list(row.feed_categories),
        portrait=portrait_of(row),
        interview=memory_of(row),
        follows=follows_of(row),
        updated_day=row.updated_day,
    )
    out.completeness = completeness(out)
    return out


def apply_patch(db: Session, row: m.StudentProfile, patch: ProfilePatch) -> None:
    """Change only the fields the patch sets (`null` clears). Raises `UnknownProgramError`."""
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
    if "portrait" in sent:
        row.portrait = patch.portrait.model_dump() if patch.portrait else {}
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


def profile_brief(row: m.StudentProfile) -> dict[str, Any]:
    """What the agents read about the student (no account data: no username, no email)."""
    portrait = portrait_of(row)
    data: dict[str, Any] = {
        "class_year": row.class_year,
        "intended_programs": list(row.intended_programs),
        "interests": list(row.interests),
        "research_areas": list(row.research_areas),
        "humanities_goal": row.humanities_goal,
        "humanities_topics": list(row.humanities_topics),
        "humanities_note": row.humanities_note,
        "career_plans": row.career_plans,
        "career_paths": list(row.career_paths),
        "future_domains": list(row.future_domains),
        "constraints": list(row.constraints),
        "workload": row.workload,
    }
    if portrait.headline or portrait.summary:
        data["portrait"] = portrait.model_dump()
    return {k: v for k, v in data.items() if v not in (None, [], "")}


# ------------------------------------------------------------------------------ routes


def clean_route(db: Session, route: RouteIn) -> RouteIn:
    """The route with unknown course codes and program ids dropped, codes normalised, each
    course once, and titles filled in from the catalog."""
    codes = [normalize_code(c.code) or "" for c in route.courses]
    titles = known_courses(db, [c for c in codes if c])
    courses: list[RouteCourse] = []
    seen: set[str] = set()
    for course, code in zip(route.courses, codes, strict=True):
        if code in titles and code not in seen:
            seen.add(code)
            courses.append(course.model_copy(update={"code": code, "title": titles[code]}))
    courses.sort(key=lambda c: (c.year, QUARTER_ORDER.get(c.quarter or "", 9)))
    return route.model_copy(
        update={"courses": courses, "program_ids": existing_programs(db, route.program_ids)}
    )


QUARTER_ORDER = {"SU": 0, "AU": 1, "WI": 2, "SP": 3}


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
            # to open first, in the same transaction.
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
    """The account's dashboard data for `/account/export`: the profile (without the email,
    which the export already has from the account) and every route. JSON-ready."""
    row = find_profile(db, account_id)
    profile: dict[str, Any] | None = None
    if row is not None:
        profile = {
            "class_year": row.class_year,
            "intended_programs": list(row.intended_programs),
            "interests": list(row.interests),
            "research_areas": list(row.research_areas),
            "humanities_goal": row.humanities_goal,
            "humanities_topics": list(row.humanities_topics),
            "humanities_note": row.humanities_note,
            "career_plans": row.career_plans,
            "career_paths": list(row.career_paths),
            "future_domains": list(row.future_domains),
            "constraints": list(row.constraints),
            "workload": row.workload,
            "feed_categories": list(row.feed_categories),
            "portrait": portrait_of(row).model_dump(mode="json"),
            "interview": memory_of(row).model_dump(mode="json"),
            "follows": follows_of(row).model_dump(mode="json"),
            "updates_seen": dict(row.updates_seen or {}),
            "created_day": row.created_day.isoformat(),
            "updated_day": row.updated_day.isoformat(),
        }
    routes = [
        route_out(db, r).model_dump(mode="json", exclude={"programs"})
        for r in _routes(db, account_id)
    ]
    return {"profile": profile, "routes": routes}
