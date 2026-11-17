"""Health and version endpoints."""

from typing import Literal

import redis
import sqlalchemy as sa
from fastapi import APIRouter, Response
from planner_core import CORE_VERSION
from pydantic import BaseModel

from api import __version__
from api.config import get_settings

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    db: bool
    redis: bool


class VersionOut(BaseModel):
    version: str
    core_version: str
    git_sha: str


def check_db() -> bool:
    """One pooled connection (the health check needs no login, so it must not open a new
    engine and connection per call)."""
    from api.db.session import get_engine

    try:
        with get_engine().connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


def check_redis() -> bool:
    try:
        client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        ok = bool(client.ping())
        client.close()
        return ok
    except Exception:
        return False


@router.get("/health", response_model=HealthOut)
def health(response: Response) -> HealthOut:
    db_ok, redis_ok = check_db(), check_redis()
    ok = db_ok and redis_ok
    if not ok:
        response.status_code = 503
    return HealthOut(status="ok" if ok else "degraded", db=db_ok, redis=redis_ok)


@router.get("/version", response_model=VersionOut)
def version() -> VersionOut:
    return VersionOut(
        version=__version__, core_version=CORE_VERSION, git_sha=get_settings().git_sha
    )
