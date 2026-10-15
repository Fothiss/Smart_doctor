"""Векторное хранилище чанков на Qdrant.

Один и тот же код работает в двух режимах: локальное хранилище в каталоге (по
умолчанию, контейнеры не нужны) и сервер Qdrant по адресу из настроек. Имя коллекции
содержит размерность вектора, поэтому смена модели не смешивает разные пространства
эмбеддингов.
"""

from collections.abc import Sequence
from uuid import UUID

from qdrant_client import QdrantClient, models

from app.config.database import DatabaseSettings, QdrantMode
from app.schemas.chunk import Chunk


class VectorStoreError(Exception):
    """Хранилище недоступно или настроено несогласованно."""


def create_client(settings: DatabaseSettings) -> QdrantClient:
    """Собрать клиент Qdrant по режиму из настроек.

    Локальный путь передаётся только именованным аргументом ``path``: первый
    позиционный аргумент клиента — это ``location``, и любая строка кроме
    ``":memory:"`` трактуется как URL, то есть локальное хранилище молча
    превратилось бы в сетевое подключение.
    """
    if settings.qdrant_mode is QdrantMode.SERVER:
        return QdrantClient(url=settings.qdrant_url)
    settings.qdrant_local_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(settings.qdrant_local_path))


def _vector_size(info: object) -> int:
    """Достать размерность вектора из описания коллекции."""
    vectors = getattr(getattr(getattr(info, "config", None), "params", None), "vectors", None)
    size = getattr(vectors, "size", None)
    if size is None and isinstance(vectors, dict):
        first = next(iter(vectors.values()), None)
        size = getattr(first, "size", None)
    if not isinstance(size, int):
        raise VectorStoreError("cannot determine collection vector size")
    return size


class ChunkVectorStore:
    """Чанки в Qdrant: запись, чтение по идентификатору, сверка размерности."""

    def __init__(self, client: QdrantClient, collection: str, dimension: int) -> None:
        self._client = client
        self._collection = collection
        self._dimension = dimension

    @property
    def collection(self) -> str:
        """Имя коллекции с размерностью."""
        return self._collection

    @classmethod
    def build(cls, settings: DatabaseSettings, dimension: int) -> "ChunkVectorStore":
        """Собрать хранилище и убедиться, что коллекция готова к работе."""
        store = cls(
            client=create_client(settings),
            collection=f"{settings.qdrant_collection}__{dimension}",
            dimension=dimension,
        )
        store.ensure_collection()
        return store

    def ensure_collection(self) -> None:
        """Создать коллекцию или сверить размерность существующей.

        Расхождение размерности — явная ошибка: иначе поиск вернул бы мусор, а
        вердикт сослался бы на фрагмент, посчитанный другой моделью.
        """
        try:
            if not self._client.collection_exists(self._collection):
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=models.VectorParams(
                        size=self._dimension, distance=models.Distance.COSINE
                    ),
                )
                return
            size = _vector_size(self._client.get_collection(self._collection))
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"vector store is unavailable: {exc}") from exc
        if size != self._dimension:
            raise VectorStoreError(
                f"collection {self._collection} stores {size}-dimensional vectors, "
                f"but the model produces {self._dimension}"
            )

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        """Записать чанки вместе с их векторами."""
        if len(chunks) != len(vectors):
            raise VectorStoreError("chunks and vectors must have the same length")
        if not chunks:
            return
        points = [
            models.PointStruct(
                id=str(chunk.chunk_id),
                vector=list(vector),
                payload=chunk.model_dump(mode="json"),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            self._client.upsert(collection_name=self._collection, points=points)
        except Exception as exc:
            raise VectorStoreError(f"failed to write chunks: {exc}") from exc

    def delete_guideline(self, guideline_id: UUID) -> None:
        """Убрать чанки клинрека перед повторной индексацией.

        Идентификаторы детерминированы, поэтому совпадающие чанки вернутся с теми же
        идентификаторами, а исчезнувшие (например, после смены параметров чанкинга)
        не останутся в хранилище сиротами.
        """
        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="guideline_id",
                            match=models.MatchValue(value=str(guideline_id)),
                        )
                    ]
                ),
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to delete chunks: {exc}") from exc

    def get(self, chunk_id: UUID) -> Chunk | None:
        """Прочитать чанк по идентификатору: текст, секцию и прямоугольники."""
        try:
            records = self._client.retrieve(
                collection_name=self._collection,
                ids=[str(chunk_id)],
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to read chunk: {exc}") from exc
        if not records:
            return None
        payload = records[0].payload or {}
        return Chunk.model_validate(payload)

    def close(self) -> None:
        """Освободить хранилище: локальный режим держит каталог заблокированным."""
        self._client.close()
