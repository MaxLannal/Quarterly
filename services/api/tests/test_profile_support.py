"""Shared set-up for the dashboard tests (test_profile_*, test_routes_*, test_interview_*): a
small FAKE 2026-27 catalog (the campus agents read that year), two programs, the Core's course
lists and offering patterns. No tests here."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from api.agents.live import CAMPUS_YEAR
from api.config import get_settings
from api.db import models as m
from auth_test_support import Env, auth_env, csrf, migrated_database
from sqlalchemy.orm import Session

SOURCE = {"url": "https://example.invalid/fake-catalog", "quote": "FAKE FIXTURE"}

#: code -> (title, core tags, usual quarter)
COURSES: dict[str, tuple[str, list[str], str | None]] = {
    "PHYS 13100": ("Mechanics", ["physical_sciences"], "AU"),
    "PHYS 13200": ("Electricity and Magnetism", ["physical_sciences"], "WI"),
    "PHYS 13300": ("Waves, Optics, and Heat", ["physical_sciences"], "SP"),
    "PHYS 23410": ("Quantum Mechanics I", [], "AU"),
    "PHYS 23510": ("Quantum Mechanics II", [], "WI"),
    "PHYS 26400": ("Quantum Computing Hardware", [], "SP"),
    "CMSC 14100": ("Introduction to Computer Science I", [], "AU"),
    "CMSC 14200": ("Introduction to Computer Science II", [], "WI"),
    "CMSC 27200": ("Theory of Algorithms", [], "WI"),
    "CMSC 28100": ("Introduction to Complexity Theory", [], "SP"),
    "CMSC 25300": ("Mathematical Foundations of Machine Learning", [], "AU"),
    "HUMA 12050": ("Greece and Rome: Texts, Traditions, Transformations I", ["humanities"], "AU"),
    "HUMA 12150": ("Greece and Rome: Texts, Traditions, Transformations II", ["humanities"], "WI"),
    "HUMA 12250": (
        "Greece and Rome: Texts, Traditions, Transformations III",
        ["humanities"],
        "SP",
    ),
    "HUMA 16000": ("Media Aesthetics: Image, Text, Sound I", ["humanities"], "AU"),
    "HUMA 16100": ("Media Aesthetics: Image, Text, Sound II", ["humanities"], "WI"),
    "HUMA 16200": ("Media Aesthetics: Image, Text, Sound III", ["humanities"], "SP"),
    "SOSC 14100": ("Mind I", ["social_sciences"], "AU"),
    "SOSC 14200": ("Mind II", ["social_sciences"], "WI"),
    "SOSC 14300": ("Mind III", ["social_sciences"], "SP"),
    "CLAS 21000": ("Greek Tragedy", [], "AU"),
    "CMST 10100": ("Introduction to Film Analysis", [], "AU"),
    "CMST 24500": ("Film Theory", [], "SP"),
}
PROGRAMS = (
    ("phys-bs", "Physics (BS)", "major", "Physics"),
    ("cmsc-bs", "Computer Science (BS)", "major", "Computer Science"),
)
LISTS = {
    "huma-12050": ("HUMA 12050-12150-12250", ["HUMA 12050", "HUMA 12150", "HUMA 12250"]),
    "huma-16000": ("HUMA 16000-16100-16200", ["HUMA 16000", "HUMA 16100", "HUMA 16200"]),
    "sosc-14100": ("SOSC 14100-14200-14300", ["SOSC 14100", "SOSC 14200", "SOSC 14300"]),
}


def seed_campus(db: Session) -> None:
    db.add(m.CatalogYear(id=CAMPUS_YEAR))
    db.flush()
    ids: dict[str, int] = {}
    for code, (title, tags, _) in COURSES.items():
        subject, number = code.split(" ")
        course = m.Course(
            catalog_year=CAMPUS_YEAR,
            subject=subject,
            number=number,
            code=code,
            title=title,
            core_tags=tags,
            tags=[],
            source=SOURCE,
        )
        db.add(course)
        db.flush()
        ids[code] = course.id
    for code, (_, _, quarter) in COURSES.items():
        for q in ("AU", "WI", "SP"):
            db.add(
                m.OfferingPattern(
                    course_id=ids[code],
                    quarter=q,
                    p_offered=0.95 if q == quarter else 0.05,
                    evidence_terms=[],
                    method="fixture",
                )
            )
    for pid, name, kind, dept in PROGRAMS:
        db.add(m.Program(id=pid, name=name, type=kind, degree="BS", department=dept))
        db.flush()
        db.add(
            m.ProgramVersion(
                program_id=pid,
                catalog_year=CAMPUS_YEAR,
                rules={"id": pid, "catalog_year": CAMPUS_YEAR, "rules": {}},
                status="published",
                checksum="fixture",
                sources=[SOURCE],
            )
        )
    for name, (label, codes) in LISTS.items():
        db.add(
            m.CourseList(
                catalog_year=CAMPUS_YEAR, name=name, label=label, course_ids=[ids[c] for c in codes]
            )
        )
    db.add(
        m.CourseList(
            catalog_year=CAMPUS_YEAR,
            name="core-huma-sequences",
            label="Humanities Core sequences",
            sublists=["huma-12050", "huma-16000"],
        )
    )
    db.add(
        m.CourseList(
            catalog_year=CAMPUS_YEAR,
            name="core-sosc-sequences",
            label="Social Sciences Core sequences",
            sublists=["sosc-14100"],
        )
    )
    db.commit()


@pytest.fixture(scope="module", name="db_url")
def db_url_fixture() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture(name="env")
def env_fixture(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    monkeypatch.setattr(get_settings(), "show_unpublished_programs", False)
    with auth_env(db_url, monkeypatch) as e:
        with e.db() as db:
            seed_campus(db)
        yield e


def login(env: Env, username: str = "quiet-heron", **kwargs: Any) -> dict[str, str]:
    """Sign up (the client is then logged in); the CSRF header for writes."""
    return csrf(env.signup(username, **kwargs))


def account_id(env: Env, username: str) -> Any:
    with env.db() as db:
        return db.scalar(sa.select(m.Account.id).where(m.Account.username == username))
