"""Поиск фрагментов клинреков под вопрос чата.

Сервис не знает ни про HTTP, ни про модель: на вход приходит текст запроса и набор
клинреков, на выход — фрагменты в порядке убывания близости, уложенные в бюджет
контекста.
"""

import asyncio
import logging
from collections.abc import Sequence
from uuid import UUID

from app.clients.embeddings import Embedder
from app.clients.vector_store import ChunkVectorStore, ScoredChunk

logger = logging.getLogger(__name__)


class RetrievalService:
    """Векторный поиск с жёстким фильтром по выбранным клинрекам.

    Порог ``min_score`` по умолчанию выключен: масштаб оценок выбранной модели
    эмбеддингов не измерен, и включённый вслепую порог отсекал бы верные ответы.
    """

    def __init__(
        self,
        embedder: Embedder,
        store: ChunkVectorStore,
        top_k: int = 8,
        max_context_chars: int = 12000,
        min_score: float = 0.0,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._top_k = top_k
        self._max_context_chars = max_context_chars
        self._min_score = min_score

    async def search(self, query: str, guideline_ids: Sequence[UUID]) -> list[ScoredChunk]:
        """Найти фрагменты под запрос.

        Кодирование запроса блокирующее (инференс на CPU или GPU), поэтому выполняется
        в рабочем потоке: иначе на время эмбеддинга останавливался бы цикл событий.
        """
        if not guideline_ids:
            return []
        return await asyncio.to_thread(self._search_blocking, query, list(guideline_ids))

    def _search_blocking(self, query: str, guideline_ids: list[UUID]) -> list[ScoredChunk]:
        """Полный проход поиска в рабочем потоке."""
        vector = self._embedder.encode_query(query)
        found = self._store.search(vector, guideline_ids, self._top_k)
        if self._min_score > 0:
            found = [item for item in found if item.score >= self._min_score]
        return fit_budget(found, self._max_context_chars)


def fit_budget(items: Sequence[ScoredChunk], max_chars: int) -> list[ScoredChunk]:
    """Уложить фрагменты в бюджет контекста, отбрасывая самые слабые.

    Сильнейший фрагмент остаётся всегда, даже если он один длиннее бюджета: пустой
    контекст означал бы отказ там, где ответ, возможно, есть. Обрезка текста запрещена —
    цитата обязана дословно совпасть с чанком.
    """
    selected: list[ScoredChunk] = []
    total = 0
    for item in items:
        length = len(item.chunk.text)
        if selected and total + length > max_chars:
            break
        selected.append(item)
        total += length
    if len(selected) < len(items):
        logger.info("Context budget dropped %d fragments", len(items) - len(selected))
    return selected
