"""Схемы клинических рекомендаций (клинреков)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.icd import normalize_codes


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

    ``icd_codes`` тоже читается с пустым значением по умолчанию: манифест без кодов
    не должен считаться битым и пропадать из библиотеки. Обязательность кодов — на
    входе API, а не в модели хранения.
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
    icd_codes: list[str] = Field(
        default_factory=list,
        description="Коды МКБ-10, которые покрывает клинрек; нормализованы и без повторов",
    )
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

    @field_validator("icd_codes")
    @classmethod
    def _normalize_icd_codes(cls, value: list[str]) -> list[str]:
        """Нормализовать коды по правилам МКБ-10, отклонив код вне формата."""
        return list(normalize_codes(value))

