"""POST /verify: load the rules for the plan from Postgres, run the verifier and the trusted
certificate checker, cache the Report in Redis.

Cache key: `verify:{core_version}:{inputs_digest}:{plan_hash}`. The digest hashes the loaded
rules and catalog facts and the request options, so reseeding the catalog or publishing a new
program version changes the key and old entries simply expire. Redis is optional: when it is
down the endpoint still answers, without caching.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

import redis
from fastapi import APIRouter, Depends, HTTPException
from planner_core import CORE_VERSION, verify_checked
from planner_core.hashing import plan_hash, sha256_of
from planner_core.models import Report
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.session import get_session
from api.repo.rules import UnknownProgramsError, load_verify_inputs
from api.schemas.plans import VerifyRequest

router = APIRouter(tags=["verify"])
logger = logging.getLogger("api.verify")

CACHE_TTL_S = 3600


@lru_cache
def _redis_client(url: str) -> redis.Redis:
    return redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)


def get_cache() -> redis.Redis:
    """FastAPI dependency: the Redis client used as the report cache."""
    return _redis_client(get_settings().redis_url)


@router.post("/verify", response_model=Report)
def verify_plan(
    body: VerifyRequest,
    session: Annotated[Session, Depends(get_session)],
    cache: Annotated[redis.Redis, Depends(get_cache)],
) -> Report:
    """Verify a plan against the rules of its catalog year. The report is "valid" only if
    the independent checker accepted the solver's certificate. A program the catalog year
    does not have (or has only as an unpublished version) is a 422."""
    plan = body.plan
    try:
        rules, catalog = load_verify_inputs(
            session, plan, show_unpublished=get_settings().show_unpublished_programs
        )
    except UnknownProgramsError as exc:
        # Same shape as FastAPI's own validation errors, so clients handle one format.
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "plan", "programs", index, "program_id"],
                    "msg": f"Unknown program for catalog year {plan.catalog_year}: "
                    f"{entry.program_id}",
                    "type": "unknown_program",
                }
                for index, entry in enumerate(plan.programs)
                if entry.program_id in exc.program_ids
            ],
        ) from exc

    digest = sha256_of(
        {
            "rules": rules.model_dump(mode="json", by_alias=True),
            "catalog": catalog.model_dump(mode="json", by_alias=True),
            "options": body.options.model_dump(mode="json", by_alias=True),
        }
    )
    key = f"verify:{CORE_VERSION}:{digest}:{plan_hash(plan)}"
    try:
        cached = cache.get(key)
        if cached is not None:
            return Report.model_validate_json(cached)  # type: ignore[arg-type]
    except (redis.RedisError, OSError, ValueError):
        logger.warning("verify cache read failed; computing without the cache")

    report, problems = verify_checked(plan, rules, catalog, body.options)
    if problems:
        # The solver and the checker disagree: a bug in one of them. Never cached.
        logger.error(
            "ALERT certificate rejected by check_certificate: plan_hash=%s problems=%s",
            report.plan_hash,
            problems[:10],
        )
        return report
    try:
        cache.set(key, report.model_dump_json(by_alias=True), ex=CACHE_TTL_S)
    except (redis.RedisError, OSError):
        logger.warning("verify cache write failed; the report was not cached")
    return report
