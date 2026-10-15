"""Оркестрация индексации клинрека: текст → чанки → векторы → хранилище.

Сервис не знает про HTTP: он получает уже собранные клиенты, меняет статус в манифесте
и складывает чанки в векторное хранилище. Разбор PDF и инференс — блокирующие
операции, поэтому выполняются в рабочем потоке, а не в цикле событий.

Векторное хранилище приходит фабрикой: документ, который не удалось разобрать, не
должен открывать Qdrant и вообще касаться хранилища.
"""

import asyncio
import logging
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.clients.embeddings import Embedder, EmbeddingError
from app.clients.vector_store import ChunkVectorStore, VectorStoreError
from app.schemas.chunk import Chunk
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.chunking import ChunkingParams, build_chunks
from app.services.guidelines import GuidelineNotFoundError, GuidelineService
from app.services.pdf_text import (
    MissingTextLayerError,
    PdfTextError,
    ensure_text_layer,
    read_pages,
)

logger = logging.getLogger(__name__)

INTERRUPTED_MESSAGE = "индексация прервана перезапуском сервера"
"""Причина отказа для клинреков, застигнутых в обработке при старте процесса."""

RECONCILE_LIMIT = 10_000
"""Сколько клинреков просматривается при снятии зависших индексаций."""

StoreFactory = Callable[[], ChunkVectorStore]
"""Фабрика векторного хранилища: открывается только перед записью чанков."""


class IndexingError(Exception):
    """Базовая ошибка индексации."""


class IndexingInProgressError(IndexingError):
    """Индексация этого клинрека уже идёт."""

    def __init__(self, guideline_id: UUID) -> None:
        super().__init__(f"indexing is already running for guideline {guideline_id}")
        self.guideline_id = guideline_id


class IndexingFailedError(IndexingError):
    """Индексация невозможна: документ непригоден."""


def reconcile_interrupted(guidelines: GuidelineService) -> list[UUID]:
    """Снять клинреки, зависшие в ``processing`` после перезапуска процесса.

    Иначе такой клинрек остаётся «обрабатывается» навсегда: работы нет, а повтор
    запустить нельзя — статус занят.
    """
    interrupted: list[UUID] = []
    for guideline in guidelines.list(
        status=GuidelineStatus.PROCESSING, limit=RECONCILE_LIMIT, offset=0
    ):
        failed = guideline.model_copy(
            update={"status": GuidelineStatus.FAILED, "error": INTERRUPTED_MESSAGE}
        )
        guidelines.save(failed)
        interrupted.append(guideline.guideline_id)
    return interrupted


def _batches(items: Sequence[Chunk], size: int) -> Iterator[Sequence[Chunk]]:
    """Разбить чанки на порции для инференса."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


class GuidelineIndexer:
    """Индексатор клинреков с одним рабочим слотом.

    Один слот — не оптимизация, а необходимость: инференс на CPU занимает все ядра,
    и две параллельные индексации только замедлят друг друга, заодно сделав API
    неотзывчивым.
    """

    def __init__(
        self,
        store_factory: StoreFactory,
        embedder: Embedder,
        params: ChunkingParams | None = None,
        batch_size: int = 16,
    ) -> None:
        self._store_factory = store_factory
        self._embedder = embedder
        self._params = params or ChunkingParams()
        self._batch_size = max(1, batch_size)
        self._lock = asyncio.Lock()
        self._running: set[UUID] = set()

    def is_running(self, guideline_id: UUID) -> bool:
        """Идёт ли индексация этого клинрека прямо сейчас."""
        return guideline_id in self._running

    def mark_queued(self, guidelines: GuidelineService, guideline_id: UUID) -> Guideline:
        """Перевести клинрек в обработку, чтобы статус сменился сразу после запроса."""
        return self._update(
            guidelines, guidelines.get(guideline_id), status=GuidelineStatus.PROCESSING, error=None
        )

    async def index(self, guidelines: GuidelineService, guideline_id: UUID) -> Guideline:
        """Проиндексировать клинрек и вернуть его итоговые метаданные.

        Повторный запуск во время работы отклоняется, а не встаёт в очередь: иначе
        пользователь не поймёт, почему его повтор ничего не ускорил.
        """
        if guideline_id in self._running:
            raise IndexingInProgressError(guideline_id)
        self._running.add(guideline_id)
        try:
            async with self._lock:
                return await asyncio.to_thread(self._index_blocking, guidelines, guideline_id)
        finally:
            self._running.discard(guideline_id)

    def _index_blocking(self, guidelines: GuidelineService, guideline_id: UUID) -> Guideline:
        """Полный прогон индексации в рабочем потоке."""
        try:
            guideline, pdf_path = guidelines.get_pdf(guideline_id)
        except GuidelineNotFoundError:
            logger.warning("Guideline %s disappeared before indexing", guideline_id)
            raise

        current = self._update(
            guidelines, guideline, status=GuidelineStatus.PROCESSING, error=None
        )
        try:
            pages = read_pages(pdf_path)
            ensure_text_layer(pages)
            chunks = build_chunks(pages, guideline.guideline_id, guideline.version, self._params)
            if not chunks:
                raise IndexingFailedError("из документа не удалось собрать ни одного фрагмента")

            current = self._update(guidelines, current, chunks_total=len(chunks), chunks_indexed=0)
            store = self._store_factory()
            current = self._store_guideline(guidelines, store, chunks, current)
        except MissingTextLayerError as exc:
            return self._fail(guidelines, current, f"в PDF нет текстового слоя: {exc}")
        except IndexingFailedError as exc:
            return self._fail(guidelines, current, str(exc))
        except (PdfTextError, EmbeddingError, VectorStoreError) as exc:
            return self._fail(guidelines, current, str(exc))
        except Exception as exc:
            logger.exception("Unexpected indexing failure for %s", guideline_id)
            return self._fail(guidelines, current, f"непредвиденная ошибка индексации: {exc}")

        logger.info("Guideline indexed: id=%s chunks=%d", guideline_id, len(chunks))
        return self._update(
            guidelines,
            current,
            status=GuidelineStatus.READY,
            error=None,
            chunks_total=len(chunks),
            chunks_indexed=len(chunks),
            embedding_model=self._embedder.model_id,
            indexed_at=datetime.now(UTC),
        )

    def _store_guideline(
        self,
        guidelines: GuidelineService,
        store: ChunkVectorStore,
        chunks: Sequence[Chunk],
        current: Guideline,
    ) -> Guideline:
        """Записать чанки порциями, отмечая прогресс в манифесте."""
        store.delete_guideline(current.guideline_id)
        indexed = 0
        for batch in _batches(chunks, self._batch_size):
            vectors = self._embedder.encode_documents([chunk.text for chunk in batch])
            store.upsert(batch, vectors)
            indexed += len(batch)
            current = self._update(guidelines, current, chunks_indexed=indexed)
        return current

    def _fail(self, guidelines: GuidelineService, guideline: Guideline, message: str) -> Guideline:
        """Записать отказ индексации с причиной."""
        logger.warning("Indexing failed for %s: %s", guideline.guideline_id, message)
        return self._update(guidelines, guideline, status=GuidelineStatus.FAILED, error=message)

    def _update(
        self, guidelines: GuidelineService, guideline: Guideline, **changes: object
    ) -> Guideline:
        """Обновить метаданные клинрека и атомарно записать манифест."""
        updated = guideline.model_copy(update=changes)
        guidelines.save(updated)
        return updated
