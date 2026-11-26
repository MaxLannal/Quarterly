"""`api.agents.runtime.Citer` (moved from the removed Ask chatbot, issue #15): the Commons bot's
source chips are checked against the ids the run saw and built from the database, with the same
labels and links as before the move. Fake 2099-00 fixture only."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from api.agents import live
from api.agents.campus_tools import load_guide
from api.agents.runtime import MAX_SOURCES, CitedSource, Citer
from api.db import models as m
from api.seed.bundle import load_bundle
from api.seed.loader import upsert_bundle
from api_test_support import FIXTURES
from auth_test_support import Env, auth_env, migrated_database

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with migrated_database() as url:
        yield url


@pytest.fixture
def env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    # The campus agents read one catalog year; the fixture's is 2099-00.
    monkeypatch.setattr(live, "CAMPUS_YEAR", "2099-00")
    with auth_env(db_url, monkeypatch) as e:
        with e.db() as db:
            upsert_bundle(db, load_bundle(FIXTURES / "seed" / "2099-00"))
        yield e


def add_thread(env: Env, title: str) -> int:
    with env.db() as db:
        thread = m.CommonsThread(title=title, body_md="Body.", author_ref="someone")
        db.add(thread)
        db.commit()
        return int(thread.id)


def test_guide_thread_program_and_course_chips_are_built_from_the_id(env: Env) -> None:
    thread_id = add_thread(env, "Is TEST 10000 fun?")
    seen = {
        "guide:core-overview",
        f"thread:{thread_id}",
        "program:test-bs",
        "course:TEST 10000",
        "attribute:TEST 10000:workload_hours",
        "thread:999",
    }
    with env.db() as db:
        citer = Citer(db, seen)
        for kind, ident in [
            ("guide", "core-overview"),
            ("thread", str(thread_id)),
            ("program", "test-bs"),
            ("course", "test10000"),  # normalised to "TEST 10000"
            ("course", "TEST 10000"),  # the same chip once
            ("attribute", "TEST 10000:workload_hours"),
            ("thread", "999"),  # seen, but no such thread: dropped
            ("program", "never-returned"),  # no tool returned it: dropped
            ("spell", "x"),  # not a kind
        ]:
            citer.add(kind, ident)
        kept = {c.kind: c for c in citer.kept}
        title = db.scalar(sa.select(m.Course.title).where(m.Course.code == "TEST 10000"))
    guide = next(e for e in load_guide() if e.id == "core-overview")
    assert citer.dropped == 3
    assert kept["guide"] == CitedSource("guide", "core-overview", guide.title, guide.source_url)
    assert kept["thread"] == CitedSource(
        "thread", str(thread_id), "Forum: Is TEST 10000 fun?", f"/forum/t/{thread_id}"
    )
    assert kept["program"] == CitedSource(
        "program", "test-bs", "Test Studies BS (fake)", "/programs/test-bs"
    )
    assert kept["course"] == CitedSource(
        "course", "TEST 10000", f"TEST 10000 · {title}", "/courses/TEST%2010000"
    )
    assert kept["attribute"] == CitedSource(
        "attribute",
        "TEST 10000:workload_hours",
        "TEST 10000: workload hours",
        "/courses/TEST%2010000",
    )
    assert len(citer.kept) == 5


def test_at_most_twelve_chips(env: Env) -> None:
    ids = [add_thread(env, f"Question {i}") for i in range(MAX_SOURCES + 3)]
    with env.db() as db:
        citer = Citer(db, {f"thread:{i}" for i in ids})
        for i in ids:
            citer.add("thread", str(i))
    assert len(citer.kept) == MAX_SOURCES == 12
