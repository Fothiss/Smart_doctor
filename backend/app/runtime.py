"""Сборка долгоживущих зависимостей приложения.

Модель эмбеддингов и клиент векторного хранилища дорогие и держат состояние: веса
в памяти и эксклюзивную блокировку каталога в локальном режиме. Поэтому они создаются
один раз на процесс и лениво — приложение обязано обслуживать загрузку и просмотр
клинреков даже тогда, когда модель ещё не положена в ``ml_models``.
"""

import logging
from uuid import UUID

from app.clients.embeddings import Embedder, SentenceTransformerEmbedder
from app.clients.llm import LLMClient, build_llm_client
from app.clients.vector_store import ChunkVectorStore, VectorStoreError
from app.config import Settings
from app.services.chunking import ChunkingParams
from app.services.guidelines import GuidelineService
from app.services.indexing import GuidelineIndexer, IndexingInProgressError, reconcile_interrupted

logger = logging.getLogger(__name__)


class Runtime:
    """Клиенты и сервисы, живущие столько же, сколько процесс."""

    def __init__(
        self,
        settings: Settings,
        embedder: Embedder | None = None,
        store: ChunkVectorStore | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.guidelines = GuidelineService(
            guidelines_dir=settings.backend.guidelines_dir,
            max_upload_size_bytes=settings.backend.max_upload_size_bytes,
        )
        self._embedder = embedder
        self._store = store
        self._indexer: GuidelineIndexer | None = None
        self._llm = llm

    @property
    def embedder(self) -> Embedder:
        """Модель эмбеддингов: загружается при первом обращении, а не на старте."""
        if self._embedder is None:
            self._embedder = SentenceTransformerEmbedder(self.settings.embedding)
        return self._embedder

    @property
    def store(self) -> ChunkVectorStore:
        """Векторное хранилище: коллекция проверяется при сборке."""
        if self._store is None:
            self._store = ChunkVectorStore.build(
                self.settings.database, self.settings.embedding.dimension
            )
        return self._store

    @property
    def llm(self) -> LLMClient:
        """Клиент LLM: создаётся при первом вопросе, ключ не нужен остальным экранам.

        Лениво по той же причине, что и модель эмбеддингов: загрузка, просмотр и
        валидация формы обязаны работать без настроенного чата.
        """
        if self._llm is None:
            self._llm = build_llm_client(self.settings.llm)
        return self._llm

    @property
    def indexer(self) -> GuidelineIndexer:
        """Индексатор с одним рабочим слотом.

        Векторное хранилище передаётся фабрикой: открывается только перед записью
        чанков, поэтому непригодный документ не трогает Qdrant вообще.
        """
        if self._indexer is None:
            backend = self.settings.backend
            self._indexer = GuidelineIndexer(
                store_factory=lambda: self.store,
                embedder=self.embedder,
                params=ChunkingParams(
                    target_chars=backend.chunk_target_chars,
                    min_chars=backend.chunk_min_chars,
                    max_chars=backend.chunk_max_chars,
                    overlap_chars=backend.chunk_overlap_chars,
                ),
                batch_size=self.settings.embedding.batch_size,
            )
        return self._indexer

    def start(self) -> None:
        """Снять зависшие индексации после перезапуска процесса.

        Векторное хранилище здесь не открывается: оно нужно только индексации, а её
        недоступность не должна мешать загрузке и просмотру клинреков.
        """
        interrupted: list[UUID] = reconcile_interrupted(self.guidelines)
        if interrupted:
            logger.info("Marked %d interrupted ingestions as failed", len(interrupted))

    def is_indexing(self, guideline_id: UUID) -> bool:
        """Идёт ли индексация клинрека.

        Индексер не собирается по требованию: он тянет модель эмбеддингов, а проверка
        «идёт ли работа» не должна будить веса на несколько гигабайт.
        """
        return self._indexer is not None and self._indexer.is_running(guideline_id)

    def delete_guideline(self, guideline_id: UUID) -> None:
        """Удалить клинрек целиком: сначала чанки, затем файлы.

        Порядок — часть контракта. Если векторное хранилище недоступно, клинрек
        остаётся целым и в библиотеке, а не превращается в набор чанков без документа:
        цитата на такой фрагмент перестала бы открываться.

        Отсутствие клинрека проверяется до обращения к Qdrant, чтобы `404` не зависел
        от доступности хранилища.
        """
        if self.is_indexing(guideline_id):
            raise IndexingInProgressError(guideline_id)
        self.guidelines.get(guideline_id)
        self.store.delete_guideline(guideline_id)
        self.guidelines.delete(guideline_id)

    def close(self) -> None:
        """Освободить векторное хранилище и клиент LLM, если они открывались."""
        if self._store is not None:
            try:
                self._store.close()
            except VectorStoreError as exc:
                logger.warning("Failed to close vector store: %s", exc)
            self._store = None
        # У клиента GigaChat нет метода закрытия: соединения живут столько же, сколько процесс
        self._llm = None
