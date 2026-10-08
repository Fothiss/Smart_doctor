"""Бизнес-логика приёма и хранения клинреков."""

import hashlib
import logging
import shutil
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from app.config import settings
from app.schemas.guideline import Guideline, GuidelineStatus

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
CHUNK_SIZE = 1024 * 1024
PDF_FILENAME = "original.pdf"
META_FILENAME = "meta.json"


class GuidelineError(Exception):
    """Базовая ошибка приёма клинрека."""


class InvalidGuidelineError(GuidelineError):
    """Файл отсутствует или не является PDF."""


class GuidelineTooLargeError(GuidelineError):
    """Файл превышает допустимый размер."""


class DuplicateGuidelineError(GuidelineError):
    """PDF с таким же содержимым уже загружен."""

    def __init__(self, guideline: Guideline) -> None:
        super().__init__(f"guideline {guideline.guideline_id} has the same sha256")
        self.guideline = guideline


class GuidelineService:
    """Хранилище клинреков на локальной ФС.

    Layout: ``<storage>/guidelines/<guideline_id>/original.pdf`` + ``meta.json``.
    Слой PostgreSQL появится позже — замена локализована в этом классе.
    """

    def __init__(self, guidelines_dir: Path) -> None:
        self._dir = guidelines_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    async def create(self, upload: UploadFile, title: str | None = None) -> Guideline:
        """Сохранить загруженный PDF и вернуть его метаданные."""
        filename = Path(upload.filename or "").name
        if not filename:
            raise InvalidGuidelineError("file name is required")
        if Path(filename).suffix.lower() != ".pdf":
            raise InvalidGuidelineError("only PDF files are supported")

        guideline_id = uuid4()
        target_dir = self._dir / str(guideline_id)
        target_dir.mkdir(parents=True, exist_ok=False)
        pdf_path = target_dir / PDF_FILENAME

        digest = hashlib.sha256()
        size = 0
        is_empty = True
        try:
            with pdf_path.open("wb") as sink:
                while chunk := await upload.read(CHUNK_SIZE):
                    if is_empty:
                        if not chunk.startswith(PDF_MAGIC):
                            raise InvalidGuidelineError("file is not a PDF")
                        is_empty = False
                    size += len(chunk)
                    if size > settings.max_upload_size_bytes:
                        raise GuidelineTooLargeError(
                            f"file exceeds {settings.max_upload_size_mb} MB"
                        )
                    digest.update(chunk)
                    sink.write(chunk)

            if is_empty:
                raise InvalidGuidelineError("file is empty")

            sha256 = digest.hexdigest()
            duplicate = self._find_by_sha256(sha256)
            if duplicate is not None:
                raise DuplicateGuidelineError(duplicate)

            guideline = Guideline(
                guideline_id=guideline_id,
                version=1,
                title=title or Path(filename).stem,
                filename=filename,
                size_bytes=size,
                sha256=sha256,
                status=GuidelineStatus.UPLOADED,
                created_at=datetime.now(UTC),
            )
            (target_dir / META_FILENAME).write_text(
                guideline.model_dump_json(indent=2), encoding="utf-8"
            )
        except BaseException:
            # Не оставляем частично записанный клинрек в хранилище
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        logger.info("Guideline stored: id=%s size=%d", guideline_id, size)
        return guideline

    def _find_by_sha256(self, sha256: str) -> Guideline | None:
        """Найти клинрек с таким же содержимым (дедупликация загрузок)."""
        for meta_path in self._dir.glob(f"*/{META_FILENAME}"):
            try:
                guideline = Guideline.model_validate_json(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError) as exc:
                logger.warning("Skipping broken manifest %s: %s", meta_path, exc)
                continue
            if guideline.sha256 == sha256:
                return guideline
        return None


@lru_cache
def get_guideline_service() -> GuidelineService:
    """Сервис клинреков как зависимость FastAPI."""
    return GuidelineService(settings.guidelines_dir)
