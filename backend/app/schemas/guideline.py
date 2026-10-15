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
    """Метаданные клинрека. Хранятся рядом с PDF в ``meta.json``.

    Поля индексации необязательны: манифесты, записанные до её появления, читаются
    как есть, а статус ``uploaded`` означает, что индексация ещё не запускалась.
    """

    guideline_id: UUID
    version: int = Field(ge=1, description="Версия документа: старые отчёты привязаны к своей")
    title: str = Field(min_length=1)
    filename: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    status: GuidelineStatus
    created_at: datetime
    error: str | None = None
    chunks_total: int | None = Field(
        default=None, ge=0, description="Сколько чанков получилось при индексации"
    )
    chunks_indexed: int | None = Field(
        default=None, ge=0, description="Сколько чанков уже записано в векторное хранилище"
    )
    embedding_model: str | None = Field(
        default=None, description="Модель, которой посчитаны векторы этого клинрека"
    )
    indexed_at: datetime | None = Field(default=None, description="Когда индексация завершилась")
