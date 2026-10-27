"""Подмены внешних систем для тестов.

Модель эмбеддингов на несколько гигабайт и сетевые загрузки в тестах не нужны:
индексации достаточно детерминированного вектора нужной размерности.
"""

from collections.abc import Sequence
from hashlib import sha1
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.clients.llm import ModelRole
from app.clients.vector_store import ScoredChunk, VectorStoreError


class FakeEmbedder:
    """Детерминированный эмбеддер: одинаковый текст даёт одинаковый вектор."""

    def __init__(self, dimension: int = 8, model_id: str = "fake-embedder") -> None:
        self._dimension = dimension
        self._model_id = model_id
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    @property
    def dimension(self) -> int:
        """Размерность вектора."""
        return self._dimension

    @property
    def model_id(self) -> str:
        """Идентификатор модели для метаданных."""
        return self._model_id

    def _vector(self, text: str) -> list[float]:
        """Вектор из хеша текста: воспроизводимо и без внешних зависимостей."""
        digest = sha1(text.encode("utf-8")).digest()
        return [round(digest[index % len(digest)] / 255, 4) for index in range(self._dimension)]

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Кодировать документы и запомнить вызов."""
        self.document_calls.append(list(texts))
        return [self._vector(text) for text in texts]

    def encode_query(self, text: str) -> list[float]:
        """Кодировать запрос и запомнить вызов."""
        self.query_calls.append(text)
        return self._vector(text)


class FakeChunkStore:
    """Подмена векторного хранилища для проверок удаления клинрека."""

    def __init__(self, *, fail: bool = False) -> None:
        self.deleted: list[UUID] = []
        self._fail = fail

    def delete_guideline(self, guideline_id: UUID) -> None:
        """Запомнить удаление или отказать, если хранилище «недоступно»."""
        if self._fail:
            raise VectorStoreError("vector store is unavailable")
        self.deleted.append(guideline_id)


class FakeSearchStore:
    """Подмена поиска: отдаёт заранее заданные результаты и помнит запросы."""

    def __init__(self, results: Sequence["ScoredChunk"] = ()) -> None:
        self.results = list(results)
        self.calls: list[tuple[list[UUID], int]] = []

    def search(
        self, vector: Sequence[float], guideline_ids: Sequence[UUID], limit: int
    ) -> list["ScoredChunk"]:
        """Запомнить аргументы поиска и вернуть ближайшие результаты."""
        self.calls.append((list(guideline_ids), limit))
        return self.results[:limit]


class FakeLLM:
    """Подмена модели: отдаёт заранее заданные ответы и помнит запросы.

    Ответы расходуются по одному; исключение в очереди поднимается как есть — так
    проверяется обработка отказов провайдера.
    """

    def __init__(self, *responses: BaseModel | BaseException) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, type[BaseModel], str]] = []

    def model_for(self, role: ModelRole) -> str:
        """Имя «модели» для роли: в тестах оно лишь отражает роль."""
        return f"fake-{role}"

    async def structured(
        self,
        system: str,
        human: str,
        schema: type[BaseModel],
        *,
        role: ModelRole = ModelRole.ANSWER,
    ) -> Any:
        """Вернуть следующий заготовленный ответ."""
        self.calls.append((system, human, schema, role))
        if not self.responses:
            raise AssertionError("fake LLM ran out of responses")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response
