"""The feed's course pool: the feed-worthy courses of the latest catalog year, held in memory.

A course is feed-worthy when it is an undergraduate course (10000-29999) worth credit, has a
real description, and is not a thesis, research, reading or tutorial slot. Cross-listed copies
(the same title under several subjects) appear once. The pool is about 7,000 courses; it is
loaded once per database and catalog year and reloaded when the course table changes (a cheap
fingerprint query on every request), so ranking runs in Python without scanning descriptions
in SQL.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.db import models as m
from api.feed import text as ftext
from api.feed.categories import CATEGORIES, category_for

MIN_DESCRIPTION = 120
#: Titles of slots rather than courses: theses, research, reading courses, tutorials, CLIME.
_SLOT = re.compile(
    r"(?:\bthesis\b|\bba (?:seminar|paper|essay|project)\b|\bhonors\b|undergraduate research|"
    r"independent (?:study|research)|reading and research|^readings?:|readings? course|"
    r"directed (?:reading|research)|\btutorial\b|\bpracticum\b|\binternship\b|"
    r"collaborative learning|\bcapstone\b|senior seminar|research rotation)",
    re.IGNORECASE,
)
_GENTLE = re.compile(r"no (?:prior|previous) (?:experience|background|knowledge)|open to all")


def stable(*parts: object) -> int:
    """A stable 64-bit hash (Python's `hash` changes per process)."""
    digest = hashlib.blake2b("|".join(str(p) for p in parts).encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def jitter(*parts: object) -> float:
    """A stable number in [0, 1) for a seed and a key."""
    return stable(*parts) / 2**64


@dataclass(frozen=True)
class PoolCourse:
    id: int
    code: str
    subject: str
    number: str
    title: str
    description: str
    core_tags: tuple[str, ...]
    units: int
    category: str
    low_title: str
    low_text: str
    #: The "best of UChicago" prior: Core courses, approachable levels, rich descriptions.
    quality: float


def _quality(row: Any) -> float:
    description = str(row.description or "")
    q = min(len(description) / 450, 1.5)
    if row.core_tags:
        q += 0.8
    number = str(row.number)
    q += 1.0 if number < "20000" else 0.5
    if 6 <= len(str(row.title)) <= 60:
        q += 0.4
    if _GENTLE.search(description.lower()):
        q += 0.5
    return q


@dataclass
class Pool:
    catalog_year: str
    courses: list[PoolCourse]
    by_code: dict[str, PoolCourse] = field(default_factory=dict)
    by_category: dict[str, list[PoolCourse]] = field(default_factory=dict)
    _clouds: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    #: Other per-pool results that do not depend on the reader (a book's linked courses).
    memo: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_code = {c.code: c for c in self.courses}
        self.by_category = {cat.key: [] for cat in CATEGORIES}
        for c in self.courses:
            self.by_category[c.category].append(c)
        for rows in self.by_category.values():
            rows.sort(key=lambda c: (-c.quality, c.code))

    def cloud(self, category: str) -> list[tuple[str, int]]:
        """The category's word cloud (words of its course titles), computed once."""
        if category not in self._clouds:
            titles = [c.title for c in self.by_category.get(category, [])]
            self._clouds[category] = ftext.cloud(titles, n=28)
        return self._clouds[category]


def load_pool(db: Session, catalog_year: str) -> Pool:
    rows = db.execute(
        sa.select(
            m.Course.id,
            m.Course.code,
            m.Course.subject,
            m.Course.number,
            m.Course.title,
            m.Course.description,
            m.Course.core_tags,
            m.Course.units,
        )
        .where(
            m.Course.catalog_year == catalog_year,
            m.Course.units > 0,
            m.Course.number >= "10000",
            m.Course.number < "30000",
            sa.func.length(m.Course.description) >= MIN_DESCRIPTION,
        )
        .order_by(m.Course.code)
    ).all()
    chosen: dict[str, PoolCourse] = {}
    for row in rows:
        title = ftext.squash(str(row.title))
        if _SLOT.search(title):
            continue
        description = ftext.squash(str(row.description or ""))
        course = PoolCourse(
            id=int(row.id),
            code=str(row.code),
            subject=str(row.subject),
            number=str(row.number),
            title=title,
            description=description,
            core_tags=tuple(row.core_tags or ()),
            units=int(row.units),
            category=category_for(str(row.subject)).key,
            low_title=title.lower(),
            low_text=f"{title} {description}".lower(),
            quality=_quality(row),
        )
        key = title.casefold()
        held = chosen.get(key)
        # One copy of a cross-listed course: the one with Core tags, then the longer text.
        if held is None or (
            (bool(course.core_tags), len(course.description))
            > (bool(held.core_tags), len(held.description))
        ):
            chosen[key] = course
    return Pool(catalog_year=catalog_year, courses=sorted(chosen.values(), key=lambda c: c.code))


_LOCK = threading.Lock()
_CACHE: dict[tuple[str, str], tuple[tuple[object, ...], Pool]] = {}


def _fingerprint(db: Session, catalog_year: str) -> tuple[object, ...]:
    row = db.execute(
        sa.select(
            sa.func.count(m.Course.id),
            sa.func.max(m.Course.id),
            sa.func.sum(sa.func.length(m.Course.title)),
        ).where(m.Course.catalog_year == catalog_year)
    ).one()
    return tuple(row)


def get_pool(db: Session, catalog_year: str) -> Pool:
    """The pool for this database and catalog year, reloaded when the course table changed."""
    bind = db.get_bind()
    key = (bind.engine.url.render_as_string(hide_password=True), catalog_year)
    fingerprint = _fingerprint(db, catalog_year)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]
    pool = load_pool(db, catalog_year)
    with _LOCK:
        _CACHE[key] = (fingerprint, pool)
    return pool
