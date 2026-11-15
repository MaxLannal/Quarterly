"""Schedule pipeline test fixtures. Everything runs on the SYNTHETIC fixtures and FakeLLM: no
test sends a request to Class Search, a University site or a model provider. Each DB test gets
a throwaway database (same approach as services/api/tests/conftest.py)."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import api.db.models as m
import pytest
import sqlalchemy as sa
from alembic import command
from api.config import get_settings
from api_test_support import alembic_config
from scraper.snapshots import MemoryStore, record_snapshot
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FETCHED = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.UTC)

#: Real codes and titles copied from data/seed/2026-27 (the instructors in the fixtures are fake).
COURSES = [
    ("CMSC", "14100", "Introduction to Computer Science I"),
    ("CMSC", "14200", "Introduction to Computer Science II"),
    ("CMSC", "11111", "Creative Coding"),
    ("MADD", "21111", "Creative Coding"),
    ("MATH", "15100", "Calculus I"),
]


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def db() -> Iterator[Session]:
    base = make_url(get_settings().database_url)
    name = f"qp_test_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    except OperationalError as exc:
        admin.dispose()
        if os.environ.get("QP_ALLOW_NO_DB"):
            pytest.skip(f"no database server: {exc}")
        raise
    url = base.set(database=name).render_as_string(hide_password=False)
    try:
        command.upgrade(alembic_config(url), "head")
        engine = sa.create_engine(url)
        with Session(engine) as session:
            seed_catalog(session)
            yield session
        engine.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def seed_catalog(db: Session) -> None:
    db.add(m.CatalogYear(id="2026-27"))
    db.add(m.Term(id="2026-AU", year=2026, quarter="AU"))  # as in data/seed terms.yaml
    db.flush()
    ids = {}
    for subject, number, title in COURSES:
        row = m.Course(
            catalog_year="2026-27",
            subject=subject,
            number=number,
            code=f"{subject} {number}",
            title=title,
        )
        db.add(row)
        db.flush()
        ids[row.code] = row.id
    db.add_all(
        [
            m.CrosslistGroup(group_id="2026-27:CMSC 11111", course_id=ids["CMSC 11111"]),
            m.CrosslistGroup(group_id="2026-27:CMSC 11111", course_id=ids["MADD 21111"]),
        ]
    )
    # Fake instructors (C is missing on purpose: the fixtures spell "Demo Instrctor C").
    for letter in "ABDE":
        db.add(
            m.Instructor(
                slug=f"demo-instructor-{letter.lower()}",
                display_name=f"Demo Instructor {letter}",
                department="Demo data (fake)",
            )
        )
    db.commit()


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def html() -> Callable[[str], str]:
    """Read a SYNTHETIC fixture page by file name."""
    return fixture


@pytest.fixture
def snap(db: Session, store: MemoryStore) -> Callable[[str], int]:
    """Store a fixture page as a snapshot; returns its id."""

    def add(name: str) -> int:
        row = record_snapshot(
            db,
            store,
            url=f"synthetic://fixtures/{name}",
            body=fixture(name).encode(),
            fetched_at=FETCHED,
        )
        db.commit()
        return row.id

    return add


class FakePage:
    """Serves SYNTHETIC pages keyed by (term label, subject, page number)."""

    def __init__(self, pages: dict[tuple[str, str, int], str], terms: list[str] | None = None):
        self.pages = pages
        self.terms = terms or sorted({k[0] for k in pages})
        self.visits: list[str] = []
        self.form: dict[str, str] = {}
        self.page_no = 0

    def goto(self, url: str) -> object:
        self.visits.append(url)
        self.page_no = 0
        return None

    def select_option(self, selector: str, value: str) -> object:
        self.form[selector] = value
        return None

    def click(self, selector: str) -> None:
        self.page_no = 1 if selector == "button#search" else self.page_no + 1

    def wait_for_selector(self, selector: str) -> object:
        from scraper.dom import parse_html

        assert parse_html(self.content()).select_one(selector) is not None
        return None

    def _key(self) -> tuple[str, str, int]:
        return (self.form["select#term"], self.form["select#subject"], self.page_no)

    def content(self) -> str:
        if self.page_no == 0:
            return "<form>search form</form>"
        return self.pages[self._key()]

    def is_visible(self, selector: str) -> bool:
        return 'class="next-page"' in self.content()

    def option_values(self, selector: str) -> list[str]:
        if selector == "select#term":
            return self.terms
        return ["", *sorted({k[1] for k in self.pages})]


@pytest.fixture
def fake_site() -> FakePage:
    """A fake browser page serving the SYNTHETIC Autumn 2026 CMSC (2 pages) and MATH pages."""
    html = fixture
    return FakePage(
        {
            ("Autumn 2026", "CMSC", 1): html("SYNTHETIC_class_search_2026-AU_CMSC_p1.html"),
            ("Autumn 2026", "CMSC", 2): html("SYNTHETIC_class_search_2026-AU_CMSC_p2.html"),
            ("Autumn 2026", "MATH", 1): html("SYNTHETIC_class_search_2026-AU_MATH_p1.html"),
        }
    )
