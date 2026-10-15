"""Подмены внешних систем для тестов.

Модель эмбеддингов на несколько гигабайт и сетевые загрузки в тестах не нужны:
индексации достаточно детерминированного вектора нужной размерности.
"""

from collections.abc import Sequence
from hashlib import sha1


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
