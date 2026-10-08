"""Pydantic-модели ответов служебных эндпоинтов."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ liveness-пробы."""

    status: Literal["ok"] = "ok"
    version: str
