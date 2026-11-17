"""Fixtures for the ingestion tests: a local HTTP server serving FAKE CourseLeaf pages
(`fixtures/catalog/`), so the crawler is tested without touching the internet."""

from __future__ import annotations

import http.server
import shutil
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "catalog"


@dataclass
class CatalogServer:
    root: Path
    base_url: str
    host: str
    requests: list[tuple[str, str]] = field(default_factory=list)  # (path, user agent)

    def paths(self) -> list[str]:
        return [p for p, _ in self.requests]


@pytest.fixture
def catalog_server(tmp_path: Path) -> Iterator[CatalogServer]:
    root = tmp_path / "site"
    shutil.copytree(FIXTURES, root)
    server_ref: dict[str, CatalogServer] = {}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(root), **kwargs)  # type: ignore[arg-type]

        def do_GET(self) -> None:
            server_ref["s"].requests.append((self.path, self.headers.get("User-Agent", "")))
            super().do_GET()

        def log_message(self, format: str, *args: object) -> None:  # keep test output quiet
            return

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    host = f"127.0.0.1:{port}"
    server_ref["s"] = CatalogServer(root=root, base_url=f"http://{host}", host=host)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield server_ref["s"]
    finally:
        httpd.shutdown()
        httpd.server_close()


@dataclass
class FakeClock:
    """A clock that only moves when the crawler sleeps (so the rate limit is observable)."""

    now: float = 1000.0
    sleeps: list[float] = field(default_factory=list)

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 6))
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
