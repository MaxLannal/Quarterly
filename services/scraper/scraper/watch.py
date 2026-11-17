"""The weekly watch (SPEC "Quarterly schedule pipeline", step 1): for the next two quarters,
check whether Class Search lists the term; when it does, capture every results page, store the
snapshots, run the pipeline, and on a failed parse ask the repair agent for a proposal.

OFF unless `SCHEDULE_SCRAPER_ENABLED=true`: with the flag off it returns at once, without
starting a browser or sending any request."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from scraper.class_search import BrowserPage, CapturedPage, crawl, live_page, term_posted
from scraper.pipeline import run_schedule
from scraper.repair import propose_repair
from scraper.settings import ScraperSettings
from scraper.snapshots import SnapshotStore, record_snapshot

QUARTER_NAMES = {"AU": "Autumn", "WI": "Winter", "SP": "Spring", "SU": "Summer"}
#: Calendar order of the quarters within a calendar year (term ids use the calendar year).
ORDER = ("WI", "SP", "SU", "AU")

PageFactory = Callable[[ScraperSettings], AbstractContextManager[BrowserPage]]


def current_term(today: dt.date) -> str:
    """Jan-Mar Winter, Apr-mid Jun Spring, mid Jun-Aug Summer, Sep-Dec Autumn (approximate;
    the academic calendar is not in the seed)."""
    month = today.month
    if month <= 3:
        q = "WI"
    elif month < 6 or (month == 6 and today.day < 15):
        q = "SP"
    elif month <= 8:
        q = "SU"
    else:
        q = "AU"
    return f"{today.year}-{q}"


def upcoming_terms(today: dt.date, n: int = 2) -> list[str]:
    year, q = current_term(today).split("-")
    y, i = int(year), ORDER.index(q)
    out = []
    for _ in range(n):
        i += 1
        if i == len(ORDER):
            y, i = y + 1, 0
        out.append(f"{y}-{ORDER[i]}")
    return out


def term_label(term_id: str) -> str:
    """'2026-AU' -> 'Autumn 2026' (PLACEHOLDER: the real menu wording is not known yet)."""
    year, q = term_id.split("-")
    return f"{QUARTER_NAMES[q]} {year}"


def weekly_watch(
    db: Session,
    store: SnapshotStore,
    settings: ScraperSettings,
    llm: object,
    *,
    today: dt.date,
    page_factory: PageFactory = live_page,
) -> list[str]:
    """One weekly check. Returns a line per term saying what happened."""
    if not settings.schedule_scraper_enabled:
        return ["disabled: SCHEDULE_SCRAPER_ENABLED is not true"]
    lines: list[str] = []
    with page_factory(settings) as page:
        for term_id in upcoming_terms(today):
            label = term_label(term_id)
            if not term_posted(page, settings, label):
                lines.append(f"{term_id}: not posted yet")
                continue
            captured: list[CapturedPage] = []
            pages = crawl(page, settings, label, captured.append)
            ids = [
                record_snapshot(
                    db, store, url=c.url, body=c.html.encode(), fetched_at=c.fetched_at
                ).id
                for c in captured
            ]
            db.commit()  # keep the snapshots even if the run fails
            report = run_schedule(db, store, term_id, ids)
            db.commit()
            line = f"{term_id}: {pages} pages, run {report.run_id} {report.status}"
            if report.status == "failed":
                item = propose_repair(db, store, llm, report.run_id)
                db.commit()
                line += f", repair review item {item.id}"
            else:
                n_review = len(report.review_item_ids)
                line += f", {report.sections_written} sections, {n_review} to review"
            lines.append(line)
    return lines
