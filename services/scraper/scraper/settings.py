"""Scraper settings. The Class Search scraper is OFF unless `SCHEDULE_SCRAPER_ENABLED=true`:
the University has not confirmed that scraping is permitted (SPEC "Ask first"), so the default
must never send a request."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #: The only switch that lets the scraper (and the weekly watch) send a request.
    schedule_scraper_enabled: bool = False
    #: The guest Class Search start page. Empty by default on purpose: it must be set by hand
    #: once Richard has confirmed the University permits scraping.
    class_search_url: str = ""
    #: Seconds between page loads (SPEC: 1 request/second at most).
    scraper_delay_s: float = 1.0
    #: An honest user agent with no personal contact details.
    scraper_user_agent: str = "QuarterlyScheduleBot/0.1 (student course planner)"


class ScraperDisabledError(RuntimeError):
    """The scraper was asked to run while SCHEDULE_SCRAPER_ENABLED is not true."""


def require_enabled(settings: ScraperSettings) -> None:
    """Raise unless the scraper may send requests. Called before any browser starts."""
    if not settings.schedule_scraper_enabled:
        raise ScraperDisabledError(
            "the Class Search scraper is off (SCHEDULE_SCRAPER_ENABLED is not true); it stays "
            "off until the University confirms scraping is permitted"
        )
    if not settings.class_search_url:
        raise ScraperDisabledError("CLASS_SEARCH_URL is not set")


@lru_cache
def get_scraper_settings() -> ScraperSettings:
    return ScraperSettings()
