"""FastAPI application factory — wires interface routers onto the app."""

from fastapi import FastAPI

from app.config import settings
from app.interface.api.health import router as health_router
from app.interface.api.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router)
    app.include_router(runs_router)
    return app


app = create_app()
