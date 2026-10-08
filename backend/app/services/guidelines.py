"""Бизнес-логика приёма и хранения клинреков.

Сервис не знает про HTTP: на вход приходит поток байтов, лимит размера — из настроек.
"""

import hashlib
import logging
import shutil
from collections.abc import AsyncIterator, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.schemas.guideline import Guideline, GuidelineStatus

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
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


class GuidelineNotFoundError(GuidelineError):
    """Клинрек или запрошенная версия документа не найдены."""

    def __init__(self, guideline_id: UUID, version: int | None = None) -> None:
        message = f"guideline {guideline_id} not found"
        if version is not None:
            message = f"guideline {guideline_id} version {version} not found"
        super().__init__(message)
        self.guideline_id = guideline_id
        self.version = version


def safe_filename(raw: str) -> str:
    """Оставить только имя файла, отбросив путь с любыми разделителями.

    ``Path(...).name`` режет путь по правилам текущей ОС: на Linux обратный слэш
    разделителем не считается, поэтому имя разбирается вручную — поведение одинаково
    локально и в контейнере.
    """
    return PurePath(raw.replace("\\", "/")).name.strip()


class GuidelineService:
    """Хранилище клинреков на локальной ФС.

    Layout: ``<storage>/guidelines/<guideline_id>/original.pdf`` + ``meta.json``.
    Слой PostgreSQL появится позже — замена локализована в этом классе.
    """

    def __init__(self, guidelines_dir: Path, max_upload_size_bytes: int) -> None:
        self._dir = guidelines_dir
        self._max_upload_size_bytes = max_upload_size_bytes

    async def create(
        self,
        chunks: AsyncIterator[bytes],
        filename: str,
        title: str | None = None,
    ) -> Guideline:
        """Сохранить поток байтов PDF и вернуть метаданные клинрека."""
        filename = safe_filename(filename)
        if not filename:
            raise InvalidGuidelineError("file name is required")
        if Path(filename).suffix.lower() != ".pdf":
            raise InvalidGuidelineError("only PDF files are supported")

        guideline_id = uuid4()
        target_dir = self._dir / str(guideline_id)
        target_dir.mkdir(parents=True)
        pdf_path = target_dir / PDF_FILENAME

        digest = hashlib.sha256()
        size = 0
        is_empty = True
        try:
            with pdf_path.open("wb") as sink:
                async for chunk in chunks:
                    if is_empty:
                        if not chunk.startswith(PDF_MAGIC):
                            raise InvalidGuidelineError("file is not a PDF")
                        is_empty = False
                    size += len(chunk)
                    if size > self._max_upload_size_bytes:
                        raise GuidelineTooLargeError(
                            f"file exceeds {self._max_upload_size_bytes / (1024 * 1024):g} MB"
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

    def get(self, guideline_id: UUID, version: int | None = None) -> Guideline:
        """Прочитать метаданные клинрека.

        ``version=None`` означает последнюю (то есть единственную) версию документа.
        Битый манифест трактуется как отсутствие клинрека: он не попал в хранилище целиком.
        """
        meta_path = self._dir / str(guideline_id) / META_FILENAME
        try:
            guideline = Guideline.model_validate_json(meta_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise GuidelineNotFoundError(guideline_id, version) from None
        except (OSError, ValidationError) as exc:
            logger.warning("Skipping broken manifest %s: %s", meta_path, exc)
            raise GuidelineNotFoundError(guideline_id, version) from exc

        if version is not None and guideline.version != version:
            raise GuidelineNotFoundError(guideline_id, version)
        return guideline

    def list(
        self,
        status: GuidelineStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Guideline]:
        """Список клинреков для экрана Library: свежие загрузки первыми."""
        guidelines = [
            guideline
            for guideline in self._iter_manifests()
            if status is None or guideline.status == status
        ]
        guidelines.sort(key=lambda guideline: guideline.created_at, reverse=True)
        return guidelines[offset : offset + limit]

    def get_pdf(self, guideline_id: UUID, version: int | None = None) -> tuple[Guideline, Path]:
        """Метаданные клинрека и путь к оригинальному PDF для PDF.js."""
        guideline = self.get(guideline_id, version)
        pdf_path = self._dir / str(guideline.guideline_id) / PDF_FILENAME
        if not pdf_path.is_file():
            logger.error("Guideline %s has no PDF at %s", guideline.guideline_id, pdf_path)
            raise GuidelineNotFoundError(guideline_id, version)
        return guideline, pdf_path

    def _iter_manifests(self) -> Iterator[Guideline]:
        """Пробежать по всем манифестам хранилища, пропуская битые."""
        for meta_path in sorted(self._dir.glob(f"*/{META_FILENAME}")):
            try:
                yield Guideline.model_validate_json(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError) as exc:
                logger.warning("Skipping broken manifest %s: %s", meta_path, exc)

    def _find_by_sha256(self, sha256: str) -> Guideline | None:
        """Найти клинрек с таким же содержимым (дедупликация загрузок)."""
        for guideline in self._iter_manifests():
            if guideline.sha256 == sha256:
                return guideline
        return None
