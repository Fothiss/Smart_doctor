"""Служебные эндпоинты."""

from fastapi import APIRouter

from app.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Проверка живости сервиса")
async def health() -> HealthResponse:
    """Liveness-проба для Docker Compose."""
    return HealthResponse(version=settings.app_version)
