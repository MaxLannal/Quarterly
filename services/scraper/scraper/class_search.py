"""Playwright crawler for the public Class Search (guest access): for one term, iterate over
the subjects and capture every results page.

IMPORTANT: this has never been run against the real site, and it must not be until Richard
confirms in writing that the University permits it. `crawl` and `run_live_crawl` refuse to
start unless `SCHEDULE_SCRAPER_ENABLED=true` and `CLASS_SEARCH_URL` is set. The selectors in
`ClassSearchSite` are placeholders: they match the SYNTHETIC fixtures, not the real site
(docs/OPEN_QUESTIONS.md, "Prompt 10")."""

from __future__ import annotations

import datetime as dt
import time
import urllib.parse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from scraper.settings import ScraperSettings, require_enabled


@dataclass(frozen=True)
class ClassSearchSite:
    """How to drive the search form. PLACEHOLDERS until real pages are seen."""

    term_select: str = "select#term"
    subject_select: str = "select#subject"
    search_button: str = "button#search"
    results_marker: str = "#class-search-results"
    next_button: str = "a.next-page"


DEFAULT_SITE = ClassSearchSite()


@dataclass(frozen=True)
class CapturedPage:
    url: str  # a stable identifier: the start URL plus term, subject and page number
    term_label: str
    subject: str
    page_no: int
    html: str
    fetched_at: dt.datetime


class BrowserPage(Protocol):
    """The part of Playwright's `Page` the crawler uses (a fake in tests)."""

    def goto(self, url: str) -> object: ...

    def select_option(self, selector: str, value: str) -> object: ...

    def click(self, selector: str) -> None: ...

    def wait_for_selector(self, selector: str) -> object: ...

    def content(self) -> str: ...

    def is_visible(self, selector: str) -> bool: ...

    def option_values(self, selector: str) -> list[str]: ...


def page_url(start_url: str, term_label: str, subject: str, page_no: int) -> str:
    query = urllib.parse.urlencode({"term": term_label, "subject": subject, "page": page_no})
    return f"{start_url}#{query}"


def term_posted(page: BrowserPage, settings: ScraperSettings, term_label: str,
                site: ClassSearchSite = DEFAULT_SITE) -> bool:  # fmt: skip
    """Whether the term already appears in the search form (the weekly watch's question)."""
    require_enabled(settings)
    page.goto(settings.class_search_url)
    return term_label in page.option_values(site.term_select)


def crawl(
    page: BrowserPage,
    settings: ScraperSettings,
    term_label: str,
    sink: Callable[[CapturedPage], None],
    *,
    subjects: list[str] | None = None,
    site: ClassSearchSite = DEFAULT_SITE,
    sleep: Callable[[float], None] = time.sleep,
    max_pages_per_subject: int = 50,
) -> int:
    """Capture every results page for `term_label`; returns the number of pages. Subjects
    default to every option in the subject menu. Waits `scraper_delay_s` between loads."""
    require_enabled(settings)
    start = settings.class_search_url
    page.goto(start)
    if subjects is None:
        subjects = [s for s in page.option_values(site.subject_select) if s]
    pages = 0
    for subject in subjects:
        sleep(settings.scraper_delay_s)
        page.goto(start)
        page.select_option(site.term_select, term_label)
        page.select_option(site.subject_select, subject)
        page.click(site.search_button)
        page.wait_for_selector(site.results_marker)
        for page_no in range(1, max_pages_per_subject + 1):
            sink(
                CapturedPage(
                    url=page_url(start, term_label, subject, page_no),
                    term_label=term_label,
                    subject=subject,
                    page_no=page_no,
                    html=page.content(),
                    fetched_at=dt.datetime.now(dt.UTC),
                )
            )
            pages += 1
            if not page.is_visible(site.next_button):
                break
            sleep(settings.scraper_delay_s)
            page.click(site.next_button)
            page.wait_for_selector(site.results_marker)
    return pages


class _PlaywrightPage:  # pragma: no cover - needs Chromium and the live site
    def __init__(self, page: Any) -> None:
        self._page = page

    def goto(self, url: str) -> object:
        return self._page.goto(url)

    def select_option(self, selector: str, value: str) -> object:
        return self._page.select_option(selector, value)

    def click(self, selector: str) -> None:
        self._page.click(selector)

    def wait_for_selector(self, selector: str) -> object:
        return self._page.wait_for_selector(selector)

    def content(self) -> str:
        return str(self._page.content())

    def is_visible(self, selector: str) -> bool:
        return bool(self._page.is_visible(selector))

    def option_values(self, selector: str) -> list[str]:
        values = self._page.eval_on_selector_all(
            f"{selector} option", "els => els.map(e => e.value)"
        )
        return [str(v) for v in values]


@contextmanager
def live_page(settings: ScraperSettings) -> Iterator[BrowserPage]:  # pragma: no cover
    """A real Chromium page. Refuses unless the flag is on (checked before Playwright loads)."""
    require_enabled(settings)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(user_agent=settings.scraper_user_agent)
            yield _PlaywrightPage(context.new_page())
        finally:
            browser.close()
