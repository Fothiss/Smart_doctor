"""Бизнес-логика приёма и хранения клинреков.

Сервис не знает про HTTP: на вход приходит поток байтов, лимит размера — из настроек.
"""

import hashlib
import logging
import os
import shutil
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePath
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.icd import InvalidIcdCodeError, matches_icd, normalize_codes

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
PDF_FILENAME = "original.pdf"
META_FILENAME = "meta.json"
META_TMP_SUFFIX = ".tmp"
REPLACE_ATTEMPTS = 6
"""Сколько раз пробовать подменить манифест, если файл занят читателем."""

REPLACE_DELAY_SECONDS = 0.02
"""Пауза между попытками: блокировка на Windows краткая."""

READ_ATTEMPTS = 8
"""Сколько раз пробовать прочитать манифест, если файл занят писателем."""

READ_DELAY_SECONDS = 0.01
"""Пауза между попытками чтения."""


def _write_manifest_atomically(tmp_path: Path, target: Path, payload: str) -> None:
    """Записать временный файл и подменить манифест, переждав краткую блокировку.

    На Windows и запись, и ``os.replace`` падают с ``PermissionError``, если файл в этот
    момент кем-то открыт, а манифест читается постоянно: список библиотеки обходит все
    манифесты, интерфейс опрашивает статус каждые пару секунд, синхронизация OneDrive и
    антивирус трогают файлы независимо от нас. Блокировка короткая, поэтому несколько
    попыток надёжнее, чем сорванная индексация.
    """
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, target)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_DELAY_SECONDS)


def read_manifest_text(path: Path) -> str:
    """Прочитать манифест, переждав краткую блокировку файла писателем.

    На Windows во время подмены файла чтение может получить отказ в доступе: без повтора
    клинрек пропадает из списка библиотеки на один опрос. Отказ, который не переждать,
    пробрасывается дальше — вызывающий трактует его как битый манифест, как и раньше.
    """
    for attempt in range(READ_ATTEMPTS):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if attempt == READ_ATTEMPTS - 1:
                raise
            time.sleep(READ_DELAY_SECONDS)
    raise AssertionError("unreachable: цикл повторов завершается возвратом или исключением")


def write_manifest(path: Path, guideline: Guideline) -> None:
    """Записать манифест атомарно: временный файл рядом с целевым и ``os.replace``.

    ``os.replace`` в пределах одного каталога атомарен, поэтому читатель видит либо
    прежний манифест, либо новый. Без этого обновление статуса во время индексации
    могло бы оставить обрезанный JSON, а битый манифест означает клинрек, пропавший
    из списка библиотеки.
    """
    tmp_path = path.with_name(path.name + META_TMP_SUFFIX)
    try:
        _write_manifest_atomically(tmp_path, path, guideline.model_dump_json(indent=2))
    except BaseException:
        # Частично записанный временный файл не должен оставаться в хранилище
        tmp_path.unlink(missing_ok=True)
        raise


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


def _require_icd_codes(raw_codes: Sequence[str]) -> tuple[str, ...]:
    """Нормализовать коды МКБ, потребовав хотя бы один.

    Обязательность живёт здесь, а не в модели хранения: манифест без кодов читается,
    а создать новый клинрек без кода нельзя.
    """
    try:
        codes = normalize_codes(raw_codes)
    except InvalidIcdCodeError as exc:
        raise InvalidGuidelineError(str(exc)) from exc
    if not codes:
        raise InvalidGuidelineError("at least one ICD code is required")
    return codes


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
        *,
        icd_codes: Sequence[str],
    ) -> Guideline:
        """Сохранить поток байтов PDF и вернуть метаданные клинрека.

        Коды МКБ проверяются до чтения потока: непригодный код должен отказывать
        сразу, не дожидаясь, пока 50 МБ окажутся на диске.
        """
        filename = safe_filename(filename)
        if not filename:
            raise InvalidGuidelineError("file name is required")
        if Path(filename).suffix.lower() != ".pdf":
            raise InvalidGuidelineError("only PDF files are supported")
        normalized_codes = _require_icd_codes(icd_codes)

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
                icd_codes=list(normalized_codes),
            )
            write_manifest(target_dir / META_FILENAME, guideline)
        except BaseException:
            # Не оставляем частично записанный клинрек в хранилище
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        logger.info("Guideline stored: id=%s size=%d", guideline_id, size)
        return guideline

    def save(self, guideline: Guideline) -> None:
        """Обновить манифест клинрека атомарно.

        Нужен индексации: статус и прогресс меняются многократно, пока тот же клинрек
        читается списком библиотеки.
        """
        write_manifest(self._dir / str(guideline.guideline_id) / META_FILENAME, guideline)

    def get(self, guideline_id: UUID, version: int | None = None) -> Guideline:
        """Прочитать метаданные клинрека.

        ``version=None`` означает последнюю (то есть единственную) версию документа.
        Битый манифест трактуется как отсутствие клинрека: он не попал в хранилище целиком.
        """
        meta_path = self._dir / str(guideline_id) / META_FILENAME
        try:
            guideline = Guideline.model_validate_json(read_manifest_text(meta_path))
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
        icd: str | None = None,
    ) -> Sequence[Guideline]:
        """Список клинреков для экрана Library: свежие загрузки первыми.

        Фильтр по коду МКБ считается в памяти: манифесты и так обходятся целиком,
        а отдельный индекс на текущих объёмах не нужен.
        """
        guidelines = [
            guideline
            for guideline in self._iter_manifests()
            if (status is None or guideline.status == status)
            and (icd is None or any(matches_icd(code, icd) for code in guideline.icd_codes))
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

    def delete(self, guideline_id: UUID) -> None:
        """Удалить каталог клинрека вместе с оригиналом PDF и манифестом.

        Отсутствие клинрека — ошибка «не найден», а не молчаливый успех: если клинрек
        уже удалили в другой вкладке, интерфейс должен показать причину, а не сделать
        вид, что удаление прошло.

        Чанки в векторном хранилище этот метод не трогает: клинрек удаляется целиком
        только через рантайм, который сначала убирает векторы.
        """
        target_dir = self._dir / str(guideline_id)
        if not target_dir.is_dir():
            raise GuidelineNotFoundError(guideline_id)
        shutil.rmtree(target_dir)
        logger.info("Guideline removed: id=%s", guideline_id)

    def _iter_manifests(self) -> Iterator[Guideline]:
        """Пробежать по всем манифестам хранилища, пропуская битые."""
        for meta_path in sorted(self._dir.glob(f"*/{META_FILENAME}")):
            try:
                yield Guideline.model_validate_json(read_manifest_text(meta_path))
            except (OSError, ValidationError) as exc:
                logger.warning("Skipping broken manifest %s: %s", meta_path, exc)

    def _find_by_sha256(self, sha256: str) -> Guideline | None:
        """Найти клинрек с таким же содержимым (дедупликация загрузок)."""
        for guideline in self._iter_manifests():
            if guideline.sha256 == sha256:
                return guideline
        return None
