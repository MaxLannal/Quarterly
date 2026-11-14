"""FastAPI application factory."""

from fastapi import Depends, FastAPI

from api import __version__
from api.agents.llm import configure_llm
from api.auth.redaction import install_log_redaction
from api.auth.sessions import csrf_guard
from api.config import get_settings
from api.health import router as health_router
from api.routers import account, admin, agents, auth, catalog, forum, plans, verify


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
    )
    app.include_router(health_router)
    for module in (catalog, plans, verify, agents, forum, auth, account, admin):
        app.include_router(module.router)
    return app


app = create_app()
