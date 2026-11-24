"""The dashboard's data (`/me`): the student profile, read and written for the profile router
and the interviewing guide, plus `export_profile` for `/account/export`. (The routes were
removed in issue #15.)

The profile row is created lazily (the first read or write). The email is never stored here
(decision 5): `ProfileOut.email` is read from `account.email` each time.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.db import models as m
from api.schemas.profile import (
    MAX_TURNS,
    Follows,
    InterviewMemory,
    Portrait,
    ProfileOut,
    ProfilePatch,
    ProgramRef,
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


def today() -> dt.date:
    return dt.date.today()


# ------------------------------------------------------------------------------ profile


def find_profile(db: Session, account_id: uuid.UUID) -> m.StudentProfile | None:
    return db.get(m.StudentProfile, account_id)


def ensure_profile(db: Session, account_id: uuid.UUID) -> m.StudentProfile:
    """The account's profile, created on first use. Safe when two requests create it at once
    (two dashboard requests load together): the insert does nothing on a conflict."""
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


# ------------------------------------------------------------------------------ export


def export_profile(db: Session, account_id: uuid.UUID) -> dict[str, Any]:
    """The account's dashboard data for `/account/export`: the profile (without the email,
    which the export already has from the account). JSON-ready."""
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
    return {"profile": profile}
