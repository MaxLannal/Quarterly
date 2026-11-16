"""Hyde Park weather for the homepage's chapel scene (FEEDBACK "ASCII Scene", 2026-11-16).

The server asks Open-Meteo (free, no key) at most once every 15 minutes and serves the cached
answer. A visitor's browser only talks to this site, so Open-Meteo never sees a visitor's IP
address (CLAUDE.md: never log or leak IP addresses) and the page keeps its "no request leaves
the app's own origin" rule. The data is CC BY 4.0: the homepage credits Open-Meteo.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel

router = APIRouter(tags=["weather"])

# Rockefeller Chapel, Hyde Park, Chicago (the scene's default coordinates).
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast?latitude=41.7886&longitude=-87.5987&current=weather_code,cloud_cover"
FRESH_SECONDS = 15 * 60  # a good answer is reused for 15 minutes
RETRY_SECONDS = 5 * 60  # after a failure, wait 5 minutes before asking again
TIMEOUT_SECONDS = 3


class WeatherOut(BaseModel):
    """WMO weather code and cloud cover (percent) now in Hyde Park."""

    weather_code: int
    cloud_cover: int | None


def fetch_open_meteo() -> WeatherOut:
    """One request to Open-Meteo. Replaced in tests: tests never call the internet."""
    req = urllib.request.Request(OPEN_METEO_URL, headers={"User-Agent": "Quarterly"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:  # a fixed https URL
        body: Any = json.load(r)
    cur = body["current"]
    cover = cur.get("cloud_cover")
    return WeatherOut(
        weather_code=int(cur["weather_code"]),
        cloud_cover=None if cover is None else int(cover),
    )


class _Cache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.value: WeatherOut | None = None
        self.next_try = 0.0

    def reset(self) -> None:
        with self.lock:
            self.value, self.next_try = None, 0.0


_cache = _Cache()


def current_weather(now: float | None = None) -> WeatherOut | None:
    """The cached weather, refreshed when stale; None while Open-Meteo cannot be reached."""
    t = time.monotonic() if now is None else now
    with _cache.lock:
        if t < _cache.next_try:
            return _cache.value
        try:
            _cache.value = fetch_open_meteo()
            _cache.next_try = t + FRESH_SECONDS
        except Exception:
            # Keep the last good answer for a while; the scene falls back to clear skies.
            _cache.next_try = t + RETRY_SECONDS
        return _cache.value


@router.get(
    "/weather",
    response_model=WeatherOut,
    responses={503: {"description": "Weather is unavailable right now; show clear skies."}},
)
def weather(response: Response) -> WeatherOut | Response:
    w = current_weather()
    if w is None:
        return Response(status_code=503, headers={"Cache-Control": "no-store"})
    response.headers["Cache-Control"] = "public, max-age=600"
    return w
