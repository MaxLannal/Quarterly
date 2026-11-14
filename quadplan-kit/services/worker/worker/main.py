"""Arq worker settings: a no-op job, and the nightly forum -> attributes job (prompt 11)."""

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

    configure_llm(get_settings())
    with Session(get_engine()) as session:
        stats = run_nightly(session, get_llm())
    return f"values={stats.attributes} summaries={stats.summaries}"


class WorkerSettings:
    functions = [noop, nightly_attributes]
    cron_jobs = [cron(nightly_attributes, hour=3, minute=30, run_at_startup=False)]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    health_check_interval = 10
