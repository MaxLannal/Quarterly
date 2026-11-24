"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from api import __version__
from api.agents.llm import configure_llm
from api.auth.redaction import install_log_redaction
from api.auth.sessions import csrf_guard
from api.config import get_settings
from api.health import router as health_router
from api.routers import (
    account,
    admin,
    agents,
    auth,
    browse,
    catalog,
    commons,
    forum,
    plans,
    profile,
    updates,
    verify,
    weather,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """With RULES_CACHE_TTL_S > 0, load the catalog years before serving (prompt 12)."""
    if get_settings().rules_cache_ttl_s > 0:
        import sqlalchemy as sa
        from sqlalchemy.orm import Session

        from api.db import models as m
        from api.db.session import get_engine
        from api.repo.catalog import load_catalog
        from api.repo.rules import preload_rules_cache

        try:
            with Session(get_engine()) as session:
                preload_rules_cache(session)
                for year in session.scalars(sa.select(m.CatalogYear.id)).all():
                    load_catalog(session, year)  # the course pages' copy (counts_toward)
        except Exception as exc:  # a cold cache is only slower, never wrong
            logging.getLogger("api").warning("rules cache preload failed: %s", type(exc).__name__)
    yield


def create_app() -> FastAPI:
    # Never log email or IP addresses (CLAUDE.md): scrub every log record, process-wide.
    install_log_redaction()
    if problems := get_settings().production_problems():
        raise RuntimeError(
            "unsafe settings outside development (for local work set ENVIRONMENT=development): "
            + "; ".join(problems)
        )
    # The real LLM gateway only with LLM_LIVE=true and a provider key (CLAUDE.md API hold).
    configure_llm(get_settings())
    app = FastAPI(
        title="Quarterly API",
        version=__version__,
        separate_input_output_schemas=False,
        # A state-changing request sent with a session cookie needs the session's CSRF token.
        dependencies=[Depends(csrf_guard)],
        lifespan=lifespan,
    )
    app.include_router(health_router)
    for module in (catalog, browse, plans, verify, agents, forum, auth, account, admin, weather):
        app.include_router(module.router)
    # Campus companion (docs/BEST-OF-UCHICAGO-PLAN.md); the Ask chatbot went in issue #15.
    # The Feed went in issue #19: its spotlights and quotes are the Catalog's rows (browse).
    for module in (updates, profile, commons):
        app.include_router(module.router)
    return app


app = create_app()
