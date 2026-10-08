"""Служебные эндпоинты."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Проверка живости сервиса")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Liveness-проба для Docker Compose."""
    return HealthResponse(version=settings.backend.app_version)
