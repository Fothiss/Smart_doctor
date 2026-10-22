"""Проверки надёжности манифеста: атомарная запись и чтение во время записи."""

import os
import threading
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.guidelines import META_FILENAME, GuidelineService

ChunkStream = Callable[..., AsyncIterator[bytes]]

PARAGRAPHS = 200
"""Сколько раз обновляется манифест в проверке параллельного чтения."""


async def _create(service: GuidelineService, stream: ChunkStream, pdf: bytes) -> Guideline:
    """Создать клинрек с минимальным PDF."""
    return await service.create(stream(pdf), "klinrek.pdf", "Клинрек", icd_codes=["I10"])


def _manifest_path(service: GuidelineService, guideline: Guideline) -> Path:
    """Путь к манифесту клинрека."""
    return service._dir / str(guideline.guideline_id) / META_FILENAME


async def test_failed_write_keeps_previous_manifest(
    service: GuidelineService,
    pdf_bytes: bytes,
    stream: ChunkStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сбой при записи не портит прежний манифест и не оставляет временный файл."""
    guideline = await _create(service, stream, pdf_bytes)
    meta_path = _manifest_path(service, guideline)
    before = meta_path.read_text(encoding="utf-8")

    def broken_replace(*_: object, **__: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError, match="no space left"):
        service.save(guideline.model_copy(update={"status": GuidelineStatus.READY}))
    monkeypatch.undo()

    assert meta_path.read_text(encoding="utf-8") == before
    assert service.get(guideline.guideline_id).status is GuidelineStatus.UPLOADED
    assert list(meta_path.parent.glob("*.tmp")) == []


async def test_temporary_file_is_not_left_after_success(
    service: GuidelineService, pdf_bytes: bytes, stream: ChunkStream
) -> None:
    """Успешная запись не оставляет временных файлов рядом с манифестом."""
    guideline = await _create(service, stream, pdf_bytes)

    service.save(guideline.model_copy(update={"chunks_total": 3}))

    meta_path = _manifest_path(service, guideline)
    assert list(meta_path.parent.glob("*.tmp")) == []
    assert service.get(guideline.guideline_id).chunks_total == 3


async def test_manifest_is_readable_while_status_is_written(
    service: GuidelineService, pdf_bytes: bytes, stream: ChunkStream
) -> None:
    """Чтение списка во время постоянной записи не теряет клинрек."""
    guideline = await _create(service, stream, pdf_bytes)
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            for index in range(PARAGRAPHS):
                update = {"chunks_indexed": index, "chunks_total": PARAGRAPHS}
                service.save(guideline.model_copy(update=update))
        except BaseException as exc:
            errors.append(exc)
        finally:
            stop.set()

    thread = threading.Thread(target=writer)
    thread.start()
    seen = 0
    try:
        while not stop.is_set() or seen == 0:
            listing = service.list()
            seen += 1
            assert [item.guideline_id for item in listing] == [guideline.guideline_id]
            if seen > PARAGRAPHS * 10:
                break
    finally:
        thread.join()

    assert errors == []
    assert service.get(guideline.guideline_id).chunks_indexed == PARAGRAPHS - 1


async def test_unknown_manifest_is_not_found(service: GuidelineService) -> None:
    """Отсутствующий манифест по-прежнему трактуется как отсутствие клинрека."""
    with pytest.raises(Exception, match="not found"):
        service.get(UUID(str(uuid4())))
