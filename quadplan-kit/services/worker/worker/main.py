"""Arq worker settings: a no-op job, and the nightly forum -> attributes job (prompt 11)."""

import asyncio
import os
from typing import Any

from arq import cron
from arq.connections import RedisSettings

# Prompt 09: the annual catalog run and the monthly change check (off unless
# CATALOG_INGEST_ENABLED=true; see worker.ingest.jobs).
from worker.ingest.jobs import catalog_annual, catalog_monthly
from worker.ingest.jobs import cron_jobs as catalog_cron_jobs


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


async def startup(ctx: dict[str, Any]) -> None:
    """No emails or IP addresses in the worker's logs either (CLAUDE.md)."""
    from api.auth.redaction import install_log_redaction

    install_log_redaction()


class WorkerSettings:
    functions = [noop, nightly_attributes, catalog_annual, catalog_monthly]
    on_startup = startup
    # Up to 200 + 500 model calls a night: allow an hour (arq's default is 5 minutes).
    cron_jobs = [cron(nightly_attributes, hour=3, minute=30, run_at_startup=False, timeout=3600)]
    cron_jobs += catalog_cron_jobs()  # prompt 09
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    health_check_interval = 10
