"""Arq worker settings. One no-op job for now; agents and ingestion come later."""

import os
from typing import Any

from arq.connections import RedisSettings


async def noop(ctx: dict[str, Any]) -> str:
    """A job that does nothing; proves the queue round-trip works."""
    return "ok"


class WorkerSettings:
    functions = [noop]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    health_check_interval = 10
