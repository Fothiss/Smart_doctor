"""Сборка FastAPI-приложения."""

from fastapi import FastAPI

from app.config import settings
from app.routers import guidelines, health


def create_app() -> FastAPI:
    """Собрать приложение со всеми роутерами."""
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health.router)
    app.include_router(guidelines.router)
    return app


app = create_app()
