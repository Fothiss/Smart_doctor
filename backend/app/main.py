"""Сборка FastAPI-приложения."""

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.routers import guidelines, health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собрать приложение со всеми роутерами; настройки можно подменить в тестах."""
    settings = settings if settings is not None else get_settings()
    app = FastAPI(title=settings.backend.app_name, version=settings.backend.app_version)
    app.include_router(health.router)
    app.include_router(guidelines.router)
    return app


app = create_app()
