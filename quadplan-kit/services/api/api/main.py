"""FastAPI application factory."""

from fastapi import FastAPI

from api import __version__
from api.health import router as health_router
from api.routers import account, admin, agents, auth, catalog, forum, plans, verify


def create_app() -> FastAPI:
    app = FastAPI(title="Quarterly API", version=__version__, separate_input_output_schemas=False)
    app.include_router(health_router)
    for module in (catalog, plans, verify, agents, forum, auth, account, admin):
        app.include_router(module.router)
    return app


app = create_app()
