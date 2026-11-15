"""Crawler: robots.txt, 1 request per second, honest user agent, every response a snapshot.
Runs only against the local FAKE catalog server (conftest.py)."""

from __future__ import annotations

import hashlib
import logging

import httpx
import pytest
from worker.ingest.crawler import Crawler, CrawlerConfigError, crawl_catalog, user_agent
from worker.ingest.settings import IngestSettings
from worker.ingest.snapshots import MemoryLog, MemoryStore, SnapshotArchive

CONTACT = "catalog-bot-test@example.edu"


def make(server, clock, **kw):  # type: ignore[no-untyped-def]
    store, log = MemoryStore(), MemoryLog()
    crawler = Crawler(
        archive=SnapshotArchive(store, log),
        contact=CONTACT,
        allowed_hosts={server.host},
        clock=clock.time,
        sleep=clock.sleep,
        require_https=False,  # the local test server speaks plain http
        **kw,
    )
    return crawler, store, log


def test_the_user_agent_needs_a_contact_address() -> None:
    with pytest.raises(CrawlerConfigError, match="CATALOG_CONTACT_EMAIL"):
        user_agent("")
    agent = user_agent(CONTACT)
    assert agent.startswith("QuarterlyCatalogBot/")
    assert CONTACT in agent and "robots.txt" in agent


def test_the_crawler_refuses_to_start_without_a_contact() -> None:
    with pytest.raises(CrawlerConfigError):
        Crawler(
            archive=SnapshotArchive(MemoryStore(), MemoryLog()), contact="", allowed_hosts=set()
        )


def test_settings_are_off_by_default_and_never_faster_than_one_per_second() -> None:
    settings = IngestSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.catalog_ingest_enabled is False
    assert settings.catalog_request_interval_s == 1.0
    with pytest.raises(ValueError):
        IngestSettings(_env_file=None, catalog_request_interval_s=0.2)  # type: ignore[call-arg]


def test_crawl_obeys_robots_and_snapshots_every_response(catalog_server, clock, caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO)
    crawler, store, log = make(catalog_server, clock)
    crawl = crawl_catalog(
        crawler,
        catalog_server.base_url,
        counts_url=f"{catalog_server.base_url}/programs-study/",
    )
    paths = catalog_server.paths()
    assert paths[0] == "/robots.txt"
    assert "/thecollege/drafts/" not in paths  # disallowed by robots.txt
    assert any(s.reason == "disallowed by robots.txt" for s in crawl.skipped)
    # Links to other sites are never followed.
    assert crawler.fetch("https://elsewhere.example/thecollege/other/") is None
    assert crawler.skipped[-1].reason == "host not in the crawl list"
    # Every request sent the honest user agent.
    assert all(CONTACT in agent for _, agent in catalog_server.requests)
    # The contact address is never logged.
    assert CONTACT not in caplog.text
    # Every response (robots.txt included) became a snapshot with its sha256.
    assert len(log.rows) == len(paths) == crawler.requests
    for row in log.rows.values():
        body = store.get(str(row["storage_key"]))
        assert row["sha256"] == hashlib.sha256(body).hexdigest()
        assert str(row["storage_key"]).endswith(str(row["sha256"]))
    # Program pages come from the index, other catalog pages from the A-Z index.
    base = catalog_server.base_url
    assert set(crawl.program_pages) == {
        f"{base}/thecollege/fakescience/",
        f"{base}/thecollege/fakehistory/",
    }
    assert set(crawl.other_pages) == {f"{base}/thecollege/fakecourses/"}
    assert crawl.counts is not None and crawl.counts.status == 200


def test_at_most_one_request_per_second(catalog_server, clock) -> None:  # type: ignore[no-untyped-def]
    crawler, _, _ = make(catalog_server, clock, interval_s=0.1)  # raised to the 1 s floor
    assert crawler.interval_s == 1.0
    crawl_catalog(crawler, catalog_server.base_url)
    n = len(catalog_server.requests)
    assert n >= 5
    assert clock.sleeps == [1.0] * (n - 1)


def test_crawl_delay_in_robots_is_respected(catalog_server, clock) -> None:  # type: ignore[no-untyped-def]
    (catalog_server.root / "robots.txt").write_text("User-agent: *\nCrawl-delay: 3\n")
    crawler, _, _ = make(catalog_server, clock)
    crawler.fetch(f"{catalog_server.base_url}/azindex/")
    crawler.fetch(f"{catalog_server.base_url}/thecollege/fakehistory/")
    # robots.txt itself at the base rate, then the pages at the site's crawl delay.
    assert clock.sleeps == [3.0, 3.0]


def _mock_crawler(handler, clock, require_https=False):  # type: ignore[no-untyped-def]
    return Crawler(
        archive=SnapshotArchive(MemoryStore(), MemoryLog()),
        contact=CONTACT,
        allowed_hosts={"catalog.test"},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=clock.time,
        sleep=clock.sleep,
        require_https=require_https,
    )


def test_http_pages_are_fetched_over_https_and_other_schemes_skipped(clock) -> None:  # type: ignore[no-untyped-def]
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, html="<p>page</p>")

    crawler = _mock_crawler(handler, clock, require_https=True)
    snap = crawler.fetch("http://catalog.test/thecollege/x/")
    assert snap is not None and snap.url == "https://catalog.test/thecollege/x/"
    assert asked and all(u.startswith("https://") for u in asked)
    assert crawler.allowed("http://catalog.test/thecollege/x/")
    before = len(asked)
    assert crawler.fetch("ftp://catalog.test/thecollege/x/") is None
    assert not crawler.allowed("ftp://catalog.test/thecollege/x/")
    assert [s.reason for s in crawler.skipped] == ["not https"] and len(asked) == before


@pytest.mark.parametrize("status", [401, 403, 500])
def test_unreadable_robots_means_nothing_is_fetched(status: int, clock) -> None:  # type: ignore[no-untyped-def]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(status if request.url.path == "/robots.txt" else 200, text="page")

    crawler = _mock_crawler(handler, clock)
    assert crawler.fetch("http://catalog.test/thecollege/x/") is None
    assert seen == ["/robots.txt"]
    assert crawler.skipped[0].reason == "robots.txt could not be read"


def test_missing_robots_allows_everything(clock) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path == "/robots.txt" else 200, text="page")

    crawler = _mock_crawler(handler, clock)
    snap = crawler.fetch("http://catalog.test/thecollege/x/")
    assert snap is not None and snap.status == 200 and snap.text() == "page"


def test_network_errors_are_recorded_not_raised(clock) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        raise httpx.ConnectError("down")

    crawler = _mock_crawler(handler, clock)
    assert crawler.fetch("http://catalog.test/thecollege/x/") is None
    assert crawler.skipped[-1].reason == "request failed: ConnectError"


def test_request_limit(catalog_server, clock) -> None:  # type: ignore[no-untyped-def]
    crawler, _, _ = make(catalog_server, clock, max_requests=2)
    crawler.fetch(f"{catalog_server.base_url}/azindex/")
    with pytest.raises(CrawlerConfigError, match="request limit"):
        crawler.fetch(f"{catalog_server.base_url}/thecollege/fakehistory/")
