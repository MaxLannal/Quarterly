"""FastAPI application factory."""

from fastapi import FastAPI

from api import __version__
from api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Quarterly API", version=__version__)
    app.include_router(health_router)
    return app


app = create_app()
