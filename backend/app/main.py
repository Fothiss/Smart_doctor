"""Сборка FastAPI-приложения."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.routers import chunks, guidelines, health
from app.runtime import Runtime

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    """Собрать приложение со всеми роутерами.

    Настройки и собранные зависимости можно подменить в тестах: рантайм держит модель
    эмбеддингов и клиент векторного хранилища, а им в тестах место не всегда есть.
    """
    settings = settings if settings is not None else get_settings()
    resolved = runtime if runtime is not None else Runtime(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Снять зависшие индексации на старте и закрыть хранилище на выходе."""
        resolved.start()
        try:
            yield
        finally:
            resolved.close()

    app = FastAPI(
        title=settings.backend.app_name,
        version=settings.backend.app_version,
        lifespan=lifespan,
    )
    app.state.runtime = resolved
    app.include_router(health.router)
    app.include_router(guidelines.router)
    app.include_router(chunks.router)
    return app


app = create_app()
