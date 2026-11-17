"""Prompt 10: name matching, the +/-30% count rule, p = (k+1)/(3+2), the flag and the crawler
(against a fake browser page serving SYNTHETIC fixtures; no request is ever sent)."""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
from typing import Any

import pytest
from scraper.checks import (
    CountCheck,
    KnownInstructor,
    match_name,
    normalize_name,
    same_quarter_last_year,
    similarity,
)
from scraper.class_search import CapturedPage, crawl, live_page, term_posted
from scraper.offering import history_p
from scraper.settings import ScraperDisabledError, ScraperSettings, require_enabled
from scraper.snapshots import sigv4_headers
from scraper.watch import current_term, term_label, upcoming_terms

KNOWN = [
    KnownInstructor(1, "Demo Instructor A"),
    KnownInstructor(2, "Demo Instructor B", ("D. I. Bee",)),
    KnownInstructor(4, "Demo Instructor D"),
]


def test_names() -> None:
    assert normalize_name("Instructor, Demo D") == "demo d instructor"
    assert normalize_name("  José   O'Neil-Smith ") == "jose o neil smith"
    assert match_name("demo instructor a", KNOWN).instructor_id == 1
    assert match_name("D. I. Bee", KNOWN).instructor_id == 2  # alias
    typo = match_name("Demo Instrctor C", KNOWN)
    assert typo.outcome == "uncertain" and typo.instructor_id is None
    assert {c[0] for c in typo.candidates} == {1, 2, 4}
    assert all(0.8 <= c[2] < 1 for c in typo.candidates)
    # one letter apart is a different person: uncertain, never merged by itself
    assert match_name("Demo Instructor F", KNOWN).outcome == "uncertain"
    assert match_name("Someone Else Entirely", KNOWN).outcome == "new"
    assert similarity("Instructor, Demo A", "Demo Instructor A") == 1.0


def test_count_rule() -> None:
    assert not CountCheck("CMSC", 13, 10, "2025-AU").alert  # +30% is still inside
    assert not CountCheck("CMSC", 7, 10, "2025-AU").alert  # -30%
    assert CountCheck("CMSC", 14, 10, "2025-AU").alert
    assert CountCheck("CMSC", 6, 10, "2025-AU").alert
    assert CountCheck("CMSC", 0, 10, "2025-AU").alert
    assert not CountCheck("CMSC", 99, None, "2025-AU").alert  # no baseline, no alert
    assert CountCheck("CMSC", 5, 2, "2025-AU").change == 1.5
    assert same_quarter_last_year("2027-WI") == "2026-WI"


def test_offering_formula() -> None:
    assert [history_p(k) for k in range(4)] == [0.2, 0.4, 0.6, 0.8]
    with pytest.raises(ValueError):
        history_p(4)


def test_terms() -> None:
    assert current_term(dt.date(2026, 11, 14)) == "2026-AU"
    assert upcoming_terms(dt.date(2026, 11, 14)) == ["2027-WI", "2027-SP"]
    assert upcoming_terms(dt.date(2027, 5, 1)) == ["2027-SU", "2027-AU"]
    assert current_term(dt.date(2027, 6, 20)) == "2027-SU"
    assert current_term(dt.date(2027, 2, 1)) == "2027-WI"
    assert term_label("2026-AU") == "Autumn 2026"


# ------------------------------------------------------------------------- flag and crawler


def test_scraper_is_off_by_default(monkeypatch: pytest.MonkeyPatch, fake_site: Any) -> None:
    monkeypatch.delenv("SCHEDULE_SCRAPER_ENABLED", raising=False)
    settings = ScraperSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.schedule_scraper_enabled is False and settings.class_search_url == ""
    with pytest.raises(ScraperDisabledError, match="off"):
        require_enabled(settings)
    with pytest.raises(ScraperDisabledError, match="CLASS_SEARCH_URL"):
        require_enabled(ScraperSettings(_env_file=None, schedule_scraper_enabled=True))  # type: ignore[call-arg]
    page = fake_site
    with pytest.raises(ScraperDisabledError):
        crawl(page, settings, "Autumn 2026", lambda _: None)
    with pytest.raises(ScraperDisabledError):
        term_posted(page, settings, "Autumn 2026")
    assert page.visits == []  # refused before touching the page
    sys.modules.pop("playwright.sync_api", None)
    with pytest.raises(ScraperDisabledError), live_page(settings):
        pass
    assert "playwright.sync_api" not in sys.modules  # no browser was even loaded


def test_env_example_keeps_the_scraper_off() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / ".env.example").read_text()
    assert "SCHEDULE_SCRAPER_ENABLED=false" in text.splitlines()


ON = {"schedule_scraper_enabled": True, "class_search_url": "synthetic://class-search"}


def test_crawler_walks_subjects_and_pages(fake_site: Any) -> None:
    page = fake_site
    settings = ScraperSettings(_env_file=None, **ON)  # type: ignore[call-arg]
    got: list[CapturedPage] = []
    sleeps: list[float] = []
    assert term_posted(page, settings, "Autumn 2026")
    assert not term_posted(page, settings, "Winter 2027")
    n = crawl(page, settings, "Autumn 2026", got.append, sleep=sleeps.append)
    assert n == 3
    assert [(c.subject, c.page_no) for c in got] == [("CMSC", 1), ("CMSC", 2), ("MATH", 1)]
    assert got[0].url == "synthetic://class-search#term=Autumn+2026&subject=CMSC&page=1"
    assert "CMSC 14100" in got[0].html and "CMSC 99901" in got[1].html
    assert len(sleeps) == 3 and all(s == 1.0 for s in sleeps)  # one pause before each load
    assert set(page.visits) == {"synthetic://class-search"}


def test_sigv4_signing_is_deterministic() -> None:
    now = dt.datetime(2026, 11, 14, 12, 0, tzinfo=dt.UTC)
    kw = {
        "method": "PUT",
        "host": "localhost:9000",
        "path": "/snapshots/a/b.html",
        "body": b"<html></html>",
        "access_key": "quarterly",
        "secret_key": "secret",
        "now": now,
    }
    a, b = sigv4_headers(**kw), sigv4_headers(**kw)  # type: ignore[arg-type]
    assert a == b
    assert a["x-amz-content-sha256"] == hashlib.sha256(b"<html></html>").hexdigest()
    assert a["authorization"].startswith(
        "AWS4-HMAC-SHA256 Credential=quarterly/20261114/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature="
    )
    other = sigv4_headers(**{**kw, "secret_key": "other"})  # type: ignore[arg-type]
    assert other["authorization"] != a["authorization"]
