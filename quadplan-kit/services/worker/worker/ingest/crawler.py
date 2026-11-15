"""The catalog crawler (SPEC "Annual catalog pipeline", step 1).

- **robots.txt** is read once per host (and saved like every other response) and obeyed.
  A missing robots.txt (404) allows everything; any other failure to read it (401, 403, 5xx,
  network error) is treated as "disallow everything" for that host.
- **1 request per second** at most, across hosts, including robots.txt; a longer
  `Crawl-delay` in robots.txt wins.
- **Honest user agent** naming the project and a contact address from `.env`
  (`CATALOG_CONTACT_EMAIL`); the crawler refuses to start without one. The address is never
  logged.
- **Every response is a snapshot**: bytes to object storage, a `source_snapshot` row with its
  sha256 (see `snapshots`).
- Only the hosts it was given are fetched; links elsewhere are skipped.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import httpx

from worker.ingest import courseleaf
from worker.ingest.settings import MIN_INTERVAL_S
from worker.ingest.snapshots import Snapshot, SnapshotArchive

logger = logging.getLogger("worker.ingest.crawler")

BOT_NAME = "QuarterlyCatalogBot"
BOT_VERSION = "0.1"


class CrawlerConfigError(RuntimeError):
    pass


def user_agent(contact: str) -> str:
    contact = contact.strip()
    if "@" not in contact:
        raise CrawlerConfigError(
            "set CATALOG_CONTACT_EMAIL in .env: the crawler sends a contact address in its "
            "user agent and will not fetch anything without one"
        )
    return (
        f"{BOT_NAME}/{BOT_VERSION} (course planner for UChicago students; respects robots.txt; "
        f"1 request per second; contact: {contact})"
    )


@dataclass
class Skipped:
    url: str
    reason: str


@dataclass
class Crawler:
    archive: SnapshotArchive
    contact: str
    allowed_hosts: set[str]
    interval_s: float = MIN_INTERVAL_S
    client: httpx.Client | None = None
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    max_requests: int = 5000
    skipped: list[Skipped] = field(default_factory=list)
    requests: int = 0
    _robots: dict[str, urllib.robotparser.RobotFileParser | None] = field(default_factory=dict)
    _last: float | None = None

    def __post_init__(self) -> None:
        self.agent = user_agent(self.contact)  # refuses without a contact address
        self.interval_s = max(self.interval_s, MIN_INTERVAL_S)
        if self.client is None:
            self.client = httpx.Client(timeout=30.0, follow_redirects=False)

    # ---------------------------------------------------------------------- plumbing

    def _wait(self, delay: float) -> None:
        if self._last is not None:
            gap = self.clock() - self._last
            if gap < delay:
                self.sleep(delay - gap)
        self._last = self.clock()

    def _get(self, url: str, delay: float) -> Snapshot:
        if self.requests >= self.max_requests:
            raise CrawlerConfigError(f"request limit {self.max_requests} reached")
        self._wait(delay)
        self.requests += 1
        assert self.client is not None
        resp = self.client.get(url, headers={"User-Agent": self.agent})
        logger.info("fetched %s (%s)", url, resp.status_code)
        return self.archive.save(
            url, resp.status_code, resp.content, resp.headers.get("content-type")
        )

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            robots_url = origin + "/robots.txt"
            parser: urllib.robotparser.RobotFileParser | None
            try:
                snap = self._get(robots_url, self.interval_s)
            except httpx.HTTPError as exc:
                logger.warning("robots.txt for %s unreadable (%s): skipping host", origin, exc)
                parser = None
            else:
                parser = urllib.robotparser.RobotFileParser(robots_url)
                if snap.status == 404:
                    parser.parse([])
                elif snap.status == 200:
                    parser.parse(snap.text().splitlines())
                else:
                    logger.warning(
                        "robots.txt for %s answered %s: skipping host", origin, snap.status
                    )
                    parser = None
            self._robots[origin] = parser
        return self._robots[origin]

    def _delay_for(self, parser: urllib.robotparser.RobotFileParser) -> float:
        crawl_delay = parser.crawl_delay(self.agent)
        return max(self.interval_s, float(crawl_delay)) if crawl_delay else self.interval_s

    # ------------------------------------------------------------------------- public

    def allowed(self, url: str) -> bool:
        host = urllib.parse.urlsplit(url).netloc
        if host not in self.allowed_hosts:
            return False
        parser = self._robots_for(url)
        return parser is not None and parser.can_fetch(self.agent, url)

    def fetch(self, url: str) -> Snapshot | None:
        """The snapshot, or None (recorded in `skipped`) when the URL may not be fetched."""
        host = urllib.parse.urlsplit(url).netloc
        if host not in self.allowed_hosts:
            self.skipped.append(Skipped(url, "host not in the crawl list"))
            return None
        parser = self._robots_for(url)
        if parser is None:
            self.skipped.append(Skipped(url, "robots.txt could not be read"))
            return None
        if not parser.can_fetch(self.agent, url):
            self.skipped.append(Skipped(url, "disallowed by robots.txt"))
            return None
        try:
            return self._get(url, self._delay_for(parser))
        except httpx.HTTPError as exc:
            self.skipped.append(Skipped(url, f"request failed: {type(exc).__name__}"))
            return None


# ------------------------------------------------------------------------- catalog crawl

INDEX_PATH = "/thecollege/programsofstudy/"
AZ_PATH = "/azindex/"
#: Catalog pages worth fetching from the A-Z index: the College's program and Core pages.
PAGE_PREFIX = "/thecollege/"


@dataclass
class CatalogCrawl:
    index: Snapshot | None
    azindex: Snapshot | None
    counts: Snapshot | None
    #: Program-of-study pages listed by the index (URL -> snapshot).
    program_pages: dict[str, Snapshot] = field(default_factory=dict)
    #: Every other catalog page from the A-Z index (Core pages, course pages).
    other_pages: dict[str, Snapshot] = field(default_factory=dict)
    index_urls: list[str] = field(default_factory=list)
    az_urls: list[str] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)

    @property
    def pages(self) -> dict[str, Snapshot]:
        return {**self.program_pages, **self.other_pages}

    def all_snapshots(self) -> list[Snapshot]:
        found = [s for s in (self.index, self.azindex, self.counts) if s is not None]
        return found + list(self.pages.values())


def _ok(snap: Snapshot | None) -> bool:
    return snap is not None and snap.status == 200


def catalog_links(snap: Snapshot, base_url: str) -> list[str]:
    """Catalog page links (`/thecollege/<page>/`) in the page's main content."""
    root = courseleaf.parse_html(snap.text())
    scope = root.find(id_="textcontainer") or root.find(id_="content") or root
    host = urllib.parse.urlsplit(base_url).netloc
    out = []
    for url, _ in courseleaf.links(scope, snap.url):
        parts = urllib.parse.urlsplit(url)
        is_page = parts.netloc == host and parts.path.startswith(PAGE_PREFIX)
        if is_page and parts.path.rstrip("/") != INDEX_PATH.rstrip("/"):
            out.append(url)
    return out


def crawl_catalog(
    crawler: Crawler,
    base_url: str,
    *,
    counts_url: str | None = None,
    only: Iterable[str] | None = None,
) -> CatalogCrawl:
    """Index, A-Z index, the College's counts page, then every catalog page they list
    (`only` limits the pages to those URLs: the monthly check and tests use it)."""
    base = base_url.rstrip("/")
    index = crawler.fetch(base + INDEX_PATH)
    azindex = crawler.fetch(base + AZ_PATH)
    counts = crawler.fetch(counts_url) if counts_url else None
    crawl = CatalogCrawl(index=index, azindex=azindex, counts=counts)
    if index is not None and _ok(index):
        crawl.index_urls = catalog_links(index, base)
    if azindex is not None and _ok(azindex):
        crawl.az_urls = catalog_links(azindex, base)
    wanted = set(only) if only is not None else None
    for url in dict.fromkeys(crawl.index_urls + crawl.az_urls):
        if wanted is not None and url not in wanted:
            continue
        snap = crawler.fetch(url)
        if snap is None:
            continue
        if not _ok(snap):
            crawler.skipped.append(Skipped(url, f"answered {snap.status}"))
            continue
        target = crawl.program_pages if url in crawl.index_urls else crawl.other_pages
        target[url] = snap
    crawl.skipped = list(crawler.skipped)
    return crawl
