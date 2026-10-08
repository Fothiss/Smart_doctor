"""Схемы клинических рекомендаций (клинреков)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class GuidelineStatus(StrEnum):
    """Состояние клинрека в пайплайне ingestion."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Guideline(BaseModel):
    """Метаданные клинрека. Хранятся рядом с PDF в ``meta.json``."""

    guideline_id: UUID
    version: int = Field(ge=1, description="Версия документа: старые отчёты привязаны к своей")
    title: str = Field(min_length=1)
    filename: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    status: GuidelineStatus
    created_at: datetime
    error: str | None = None
