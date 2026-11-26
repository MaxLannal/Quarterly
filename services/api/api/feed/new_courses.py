"""Newly released courses for the Catalog page (issue #19, D2).

The seed holds one catalog year, so a comparison of catalog years cannot show new courses yet
(and `course_instructor.first_term` cannot either: it is filled only from forum activity and the
schedule scraper, which is off). So, as Richard decided on the issue:

1. A person writes the list `data/catalog/new_courses.yaml`. Each entry names a course code and
   the source that says the course is new, with a verbatim `quote` (CLAUDE.md: never invent
   catalog facts). An entry whose code is not in the catalog year is not shown.
2. When the database holds a second, earlier catalog year, the courses of the latest year that
   the year before did not have are new too (`basis: catalog`).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa
import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from api.db import models as m
from api.feed import text as ftext
from api.repo import catalog as catalog_repo
from api.schemas.browse import NewCourse

logger = logging.getLogger("api.feed")

#: The most courses the row shows.
MAX_NEW = 24
EXCERPT = 300


class ListedSource(BaseModel):
    url: str = Field(pattern=r"^https://")
    #: Copied verbatim from the page; it must say that the course is new.
    quote: str = Field(min_length=1)
    fetched: dt.date | None = None


class ListedCourse(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2,5} \d{5}$")
    source: ListedSource


class NewCoursesFile(BaseModel):
    catalog_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    courses: list[ListedCourse] = []

    @field_validator("courses")
    @classmethod
    def _unique(cls, courses: list[ListedCourse]) -> list[ListedCourse]:
        codes = [c.code for c in courses]
        if len(set(codes)) != len(codes):
            raise ValueError("new_courses.yaml: a course is listed twice")
        return courses


def new_courses_path() -> Path | None:
    """`NEW_COURSES_FILE` if set, else `data/catalog/new_courses.yaml` in the nearest folder
    above this file or the working directory (the repository root; `/app/data` in the API
    image). None when there is no such file."""
    explicit = os.environ.get("NEW_COURSES_FILE")
    if explicit:
        return Path(explicit)
    for base in (Path(__file__).resolve(), Path.cwd()):
        for folder in (base, *base.parents):
            candidate = folder / "data" / "catalog" / "new_courses.yaml"
            if candidate.is_file():
                return candidate
    return None


@lru_cache(maxsize=4)
def _load(path: str, stamp: tuple[int, int]) -> NewCoursesFile:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return NewCoursesFile.model_validate(raw)


def load_listed(*, strict: bool = False) -> NewCoursesFile | None:
    """The hand-written list, read again when the file changes (its time and size). A missing
    or broken file shows no listed courses (logged), so the other rows still load; `strict`
    raises instead (tests)."""
    path = new_courses_path()
    if path is None:
        return None
    try:
        stat = path.stat()
        return _load(str(path), (stat.st_mtime_ns, stat.st_size))
    except (OSError, ValidationError, yaml.YAMLError) as exc:
        if strict:
            raise
        logger.warning("new_courses.yaml not used: %s", type(exc).__name__)
        return None


def _rows(db: Session, year: str, codes: list[str]) -> dict[str, m.Course]:
    if not codes:
        return {}
    rows = db.scalars(
        sa.select(m.Course).where(m.Course.catalog_year == year, m.Course.code.in_(codes))
    ).all()
    return {r.code: r for r in rows}


def _new(row: m.Course, **extra: object) -> NewCourse:
    return NewCourse.model_validate(
        {
            "code": row.code,
            "title": ftext.squash(row.title),
            "units": row.units,
            "core_tags": list(row.core_tags or []),
            "excerpt": ftext.excerpt(row.description, EXCERPT),
            **extra,
        }
    )


def _listed(db: Session, year: str) -> list[NewCourse]:
    listed = load_listed()
    if listed is None or listed.catalog_year != year:
        return []
    rows = _rows(db, year, [c.code for c in listed.courses])
    out: list[NewCourse] = []
    for entry in listed.courses:
        row = rows.get(entry.code)
        if row is None:
            logger.warning("new_courses.yaml: %s is not in the %s catalog", entry.code, year)
            continue
        out.append(
            _new(
                row,
                basis="listed",
                reason=f"New in {year}",
                source_url=entry.source.url,
                source_quote=entry.source.quote,
            )
        )
    return out


#: An earlier catalog year counts only when it holds at least this share of the latest year's
#: courses: a year with a few rows (one program's ingestion, one review batch) is no catalog.
MIN_SHARE = 0.5


def _count(db: Session, year: str) -> int:
    return int(db.scalar(sa.select(sa.func.count()).where(m.Course.catalog_year == year)) or 0)


def _previous_year(db: Session, year: str) -> str | None:
    """The catalog year before `year` that has courses (read from `course`, like the latest
    year), or None when there is none or it is too small to compare with."""
    before = db.scalar(
        sa.select(sa.func.max(m.Course.catalog_year)).where(m.Course.catalog_year < year)
    )
    if before is None or _count(db, before) < MIN_SHARE * _count(db, year):
        return None
    return str(before)


def _from_catalog(db: Session, year: str, exclude: set[str]) -> list[NewCourse]:
    before = _previous_year(db, year)
    if before is None:
        return []
    earlier = sa.select(m.Course.code).where(m.Course.catalog_year == before)
    rows = db.scalars(
        sa.select(m.Course)
        .where(m.Course.catalog_year == year, m.Course.code.not_in(earlier))
        .order_by(m.Course.code)
        .limit(MAX_NEW + len(exclude))
    ).all()
    return [
        _new(row, basis="catalog", reason=f"Not in the {before} catalog")
        for row in rows
        if row.code not in exclude
    ]


def new_courses(db: Session) -> list[NewCourse]:
    """The newly released courses of the latest catalog year: listed ones first."""
    year = catalog_repo.latest_catalog_year(db)
    if year is None:
        return []
    listed = _listed(db, year)
    found = _from_catalog(db, year, {c.code for c in listed})
    return (listed + found)[:MAX_NEW]
