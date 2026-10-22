"""Проверки сервиса индексации: прогон, отказы, один слот, восстановление."""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import uuid4

import pytest
from fakes import FakeEmbedder

from app.clients.embeddings import EmbeddingError, SentenceTransformerEmbedder
from app.clients.vector_store import ChunkVectorStore, VectorStoreError
from app.config import EmbeddingSettings
from app.schemas.guideline import GuidelineStatus
from app.services.chunking import ChunkingParams
from app.services.guidelines import GuidelineService
from app.services.indexing import (
    INTERRUPTED_MESSAGE,
    GuidelineIndexer,
    IndexingInProgressError,
    reconcile_interrupted,
)

ChunkStream = Callable[..., AsyncIterator[bytes]]

PARAMS = ChunkingParams(target_chars=200, min_chars=100, max_chars=400)


def _indexer(
    service: GuidelineService,
    store: ChunkVectorStore,
    embedder: object,
) -> GuidelineIndexer:
    """Индексатор с хранилищем из фикстуры."""
    return GuidelineIndexer(
        store_factory=lambda: store, embedder=embedder, params=PARAMS, batch_size=2
    )


async def _upload(
    service: GuidelineService, pdf: Path, stream: ChunkStream, title: str = "Клинрек"
) -> object:
    """Загрузить PDF из файла через сервис клинреков."""
    return await service.create(stream(pdf.read_bytes()), pdf.name, title, icd_codes=["I10"])


async def test_successful_run_marks_ready_and_stores_chunks(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    fake_embedder: FakeEmbedder,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """После прогона статус `ready`, чанки записаны и доступны по идентификатору."""
    guideline = await _upload(service, mini_pdf, stream)
    indexer = _indexer(service, memory_store, fake_embedder)

    result = await indexer.index(service, guideline.guideline_id)

    assert result.status is GuidelineStatus.READY
    assert result.error is None
    assert result.embedding_model == fake_embedder.model_id
    assert result.indexed_at is not None
    assert result.chunks_total and result.chunks_total > 0
    assert result.chunks_indexed == result.chunks_total
    stored = service.get(guideline.guideline_id)
    assert stored.status is GuidelineStatus.READY


async def test_progress_is_written_during_run(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    fake_embedder: FakeEmbedder,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Во время прогона в манифест пишется число обработанных чанков."""
    guideline = await _upload(service, mini_pdf, stream)
    indexer = _indexer(service, memory_store, fake_embedder)
    seen: list[int] = []
    original_save = service.save

    def spy_save(saved: object) -> None:
        chunks_indexed = getattr(saved, "chunks_indexed", None)
        if chunks_indexed is not None:
            seen.append(chunks_indexed)
        original_save(saved)  # type: ignore[arg-type]

    service.save = spy_save  # type: ignore[method-assign]
    await indexer.index(service, guideline.guideline_id)

    assert seen, "прогресс не записывался"
    assert seen == sorted(seen)
    assert seen[0] == 0
    assert seen[-1] == service.get(guideline.guideline_id).chunks_total


async def test_scan_without_text_layer_fails(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    fake_embedder: FakeEmbedder,
    scanned_pdf: Path,
    stream: ChunkStream,
) -> None:
    """PDF без текстового слоя даёт `failed` с причиной про текстовый слой."""
    guideline = await _upload(service, scanned_pdf, stream)
    indexer = _indexer(service, memory_store, fake_embedder)

    result = await indexer.index(service, guideline.guideline_id)

    assert result.status is GuidelineStatus.FAILED
    assert result.error is not None
    assert "текстового слоя" in result.error


async def test_missing_model_files_fail(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    mini_pdf: Path,
    stream: ChunkStream,
    tmp_path: Path,
) -> None:
    """Отсутствие файлов модели даёт `failed` с различимой причиной."""
    guideline = await _upload(service, mini_pdf, stream)
    embedder = SentenceTransformerEmbedder(
        EmbeddingSettings(ml_models_dir=tmp_path / "models", model_path=Path("absent"))
    )
    indexer = _indexer(service, memory_store, embedder)

    result = await indexer.index(service, guideline.guideline_id)

    assert result.status is GuidelineStatus.FAILED
    assert result.error is not None
    assert "not found" in result.error


async def test_store_failure_fails_with_reason(
    service: GuidelineService,
    fake_embedder: FakeEmbedder,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Сбой векторного хранилища не оставляет статус `ready`."""
    guideline = await _upload(service, mini_pdf, stream)

    def broken_store() -> ChunkVectorStore:
        raise VectorStoreError("vector store is unavailable: connection refused")

    indexer = GuidelineIndexer(
        store_factory=broken_store, embedder=fake_embedder, params=PARAMS, batch_size=2
    )

    result = await indexer.index(service, guideline.guideline_id)

    assert result.status is GuidelineStatus.FAILED
    assert result.error is not None
    assert "unavailable" in result.error


async def test_embedding_failure_fails_with_reason(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Ошибка модели эмбеддингов переводит клинрек в `failed`."""

    class BrokenEmbedder(FakeEmbedder):
        def encode_documents(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingError("failed to encode text: out of memory")

    guideline = await _upload(service, mini_pdf, stream)
    indexer = _indexer(service, memory_store, BrokenEmbedder())

    result = await indexer.index(service, guideline.guideline_id)

    assert result.status is GuidelineStatus.FAILED
    assert result.error is not None
    assert "out of memory" in result.error


async def test_second_run_is_rejected_while_first_is_running(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Вторая индексация того же клинрека не начинается, пока идёт первая."""
    guideline = await _upload(service, mini_pdf, stream)
    started = asyncio.Event()

    class SlowEmbedder(FakeEmbedder):
        def encode_documents(self, texts: list[str]) -> list[list[float]]:
            started.set()
            return super().encode_documents(texts)

    indexer = _indexer(service, memory_store, SlowEmbedder())
    first = asyncio.create_task(indexer.index(service, guideline.guideline_id))
    await started.wait()

    with pytest.raises(IndexingInProgressError):
        await indexer.index(service, guideline.guideline_id)

    await first


async def test_mark_queued_sets_processing(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    fake_embedder: FakeEmbedder,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Повторный запуск сразу переводит клинрек в обработку."""
    guideline = await _upload(service, mini_pdf, stream)
    indexer = _indexer(service, memory_store, fake_embedder)

    queued = indexer.mark_queued(service, guideline.guideline_id)

    assert queued.status is GuidelineStatus.PROCESSING
    assert indexer.is_running(guideline.guideline_id) is False


async def test_interrupted_processing_is_reconciled(
    service: GuidelineService,
    mini_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Клинрек, застигнутый в обработке, переводится в `failed` при старте."""
    guideline = await _upload(service, mini_pdf, stream)
    service.save(guideline.model_copy(update={"status": GuidelineStatus.PROCESSING}))

    interrupted = reconcile_interrupted(service)

    assert interrupted == [guideline.guideline_id]
    stored = service.get(guideline.guideline_id)
    assert stored.status is GuidelineStatus.FAILED
    assert stored.error == INTERRUPTED_MESSAGE


async def test_reconcile_leaves_other_statuses_alone(
    service: GuidelineService,
    mini_pdf: Path,
    scanned_pdf: Path,
    stream: ChunkStream,
) -> None:
    """Реконсиляция не трогает клинреки в других состояниях."""
    uploaded = await _upload(service, mini_pdf, stream, title="Первый")
    # Второй PDF отличается содержимым: одинаковый не примет дедупликация по sha256
    ready = await _upload(service, scanned_pdf, stream, title="Второй")
    service.save(ready.model_copy(update={"status": GuidelineStatus.READY}))

    interrupted = reconcile_interrupted(service)

    assert interrupted == []
    assert service.get(uploaded.guideline_id).status is GuidelineStatus.UPLOADED
    assert service.get(ready.guideline_id).status is GuidelineStatus.READY


async def test_unknown_guideline_is_not_indexed(
    service: GuidelineService,
    memory_store: ChunkVectorStore,
    fake_embedder: FakeEmbedder,
) -> None:
    """Индексация неизвестного клинрека падает, а не создаёт мусор."""
    indexer = _indexer(service, memory_store, fake_embedder)

    with pytest.raises(Exception, match="not found"):
        await indexer.index(service, uuid4())
