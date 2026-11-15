"""Arq worker settings: a no-op job, and the nightly forum -> attributes job (prompt 11)."""

import asyncio
import os
from typing import Any

from arq import cron
from arq.connections import RedisSettings


async def noop(ctx: dict[str, Any]) -> str:
    """A job that does nothing; proves the queue round-trip works."""
    return "ok"


async def nightly_attributes(ctx: dict[str, Any]) -> str:
    """Forum ratings -> course attributes and "What students say" (api.attributes.job)."""
    from api.agents.llm import configure_llm
    from api.attributes.job import run_nightly
    from api.config import get_settings
    from api.db.session import get_engine
    from llm_gateway.api import get_llm
    from sqlalchemy.orm import Session

    def run() -> str:
        configure_llm(get_settings())
        with Session(get_engine()) as session:
            stats = run_nightly(session, get_llm())
        return f"values={stats.attributes} summaries={stats.summaries}"

    # The job is synchronous (database and model calls): run it in a thread so the worker's
    # event loop and health check keep going.
    return await asyncio.to_thread(run)


async def weekly_schedule_watch(ctx: dict[str, Any]) -> str:
    """Prompt 10: the weekly Class Search watch (scraper.watch). Returns at once, sending no
    request, unless SCHEDULE_SCRAPER_ENABLED=true. The crawl needs Chromium, which only the
    scraper image installs (docs/OPEN_QUESTIONS.md, "Prompt 10")."""
    from scraper.settings import get_scraper_settings

    settings = get_scraper_settings()
    if not settings.schedule_scraper_enabled:
        return "disabled: SCHEDULE_SCRAPER_ENABLED is not true"

    def run() -> str:  # pragma: no cover - needs the live site, which stays off
        import datetime as dt

        from api.agents.llm import configure_llm
        from api.config import get_settings
        from api.db.session import get_engine
        from llm_gateway.api import get_llm
        from scraper.snapshots import minio_store_from_settings
        from scraper.watch import weekly_watch
        from sqlalchemy.orm import Session

        configure_llm(get_settings())
        with Session(get_engine()) as session:
            lines = weekly_watch(
                session,
                minio_store_from_settings(),
                settings,
                get_llm(),
                today=dt.date.today(),
            )
        return "; ".join(lines)

    return await asyncio.to_thread(run)  # pragma: no cover


async def startup(ctx: dict[str, Any]) -> None:
    """No emails or IP addresses in the worker's logs either (CLAUDE.md)."""
    from api.auth.redaction import install_log_redaction

    install_log_redaction()


class WorkerSettings:
    functions = [noop, nightly_attributes]
    on_startup = startup
    # Up to 200 + 500 model calls a night: allow an hour (arq's default is 5 minutes).
    cron_jobs = [cron(nightly_attributes, hour=3, minute=30, run_at_startup=False, timeout=3600)]
    # Prompt 10: the schedule watch, Mondays 04:00 (a no-op unless SCHEDULE_SCRAPER_ENABLED).
    functions += [weekly_schedule_watch]
    cron_jobs += [
        cron(weekly_schedule_watch, weekday=0, hour=4, minute=0, run_at_startup=False, timeout=7200)
    ]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    health_check_interval = 10
