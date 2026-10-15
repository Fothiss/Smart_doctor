"""Провайдеры зависимостей API-слоя.

Клиенты, живущие столько же, сколько процесс (модель эмбеддингов, векторное
хранилище), берутся из состояния приложения: собирать их на каждый запрос нельзя —
модель занимает память, а локальный Qdrant держит каталог заблокированным.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.runtime import Runtime
from app.services.guidelines import GuidelineService

RUNTIME_STATE_ATTR = "runtime"
"""Имя атрибута состояния FastAPI, в котором лежит собранный :class:`Runtime`."""


def get_runtime(request: Request) -> Runtime:
    """Достать собранные зависимости приложения из состояния FastAPI."""
    runtime = getattr(request.app.state, RUNTIME_STATE_ATTR, None)
    if runtime is None:
        raise RuntimeError("application runtime is not initialised")
    return runtime


def get_guideline_service(
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> GuidelineService:
    """Сервис клинреков — провайдер зависимостей API-слоя."""
    return runtime.guidelines
