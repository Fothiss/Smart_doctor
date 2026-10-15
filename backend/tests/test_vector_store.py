"""Проверки векторного хранилища: коллекция, размерность, запись и чтение чанков."""

from pathlib import Path
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient, models

from app.clients.vector_store import ChunkVectorStore, VectorStoreError, create_client
from app.config import DatabaseSettings, QdrantMode
from app.schemas.chunk import Chunk, ChunkRect

GUIDELINE_ID = uuid4()


def _chunk(text: str, page: int = 3, extra_page: int | None = None) -> Chunk:
    """Чанк с прямоугольниками на одной или двух страницах."""
    rects = [ChunkRect(page=page, bbox=(72.0, 700.0, 500.0, 712.0))]
    if extra_page is not None:
        rects.append(ChunkRect(page=extra_page, bbox=(72.0, 100.0, 400.0, 180.0)))
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=GUIDELINE_ID,
        guideline_version=1,
        section="2. Диагностика",
        text=text,
        chunk_index=0,
        page=rects[0].page,
        bbox=rects[0].bbox,
        rects=rects,
    )


def test_local_client_uses_directory_not_network(tmp_path: Path) -> None:
    """Локальный режим создаёт каталог, а не пытается соединиться по строке пути."""
    settings = DatabaseSettings(
        qdrant_mode=QdrantMode.LOCAL, qdrant_local_path=tmp_path / "qdrant"
    )

    client = create_client(settings)

    try:
        assert settings.qdrant_local_path.is_dir()
        assert client.collection_exists("absent") is False
    finally:
        client.close()


def test_collection_name_contains_dimension(memory_store: ChunkVectorStore) -> None:
    """Имя коллекции включает размерность: разные модели не смешиваются."""
    assert memory_store.collection.endswith("__8")


def test_dimension_mismatch_is_reported() -> None:
    """Расхождение размерности даёт явную ошибку, а не тихий мусор в поиске."""
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="mismatch__4",
        vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE),
    )
    store = ChunkVectorStore(client=client, collection="mismatch__4", dimension=8)

    with pytest.raises(VectorStoreError, match="4-dimensional"):
        store.ensure_collection()


def test_chunks_round_trip(memory_store: ChunkVectorStore) -> None:
    """Записанный чанк читается вместе с текстом, секцией и прямоугольниками."""
    chunk = _chunk("Измерение давления на обеих руках.", page=5, extra_page=6)
    vector = [0.1] * memory_store._dimension

    memory_store.upsert([chunk], [vector])
    loaded = memory_store.get(chunk.chunk_id)

    assert loaded is not None
    assert loaded.chunk_id == chunk.chunk_id
    assert loaded.text == chunk.text
    assert loaded.section == "2. Диагностика"
    assert [rect.page for rect in loaded.rects] == [5, 6]
    assert loaded.page == 5
    assert loaded.bbox == chunk.bbox


def test_unknown_chunk_is_none(memory_store: ChunkVectorStore) -> None:
    """Неизвестный идентификатор не поднимает исключение."""
    assert memory_store.get(uuid4()) is None


def test_vectors_and_chunks_must_match(memory_store: ChunkVectorStore) -> None:
    """Число векторов обязано совпадать с числом чанков."""
    with pytest.raises(VectorStoreError, match="same length"):
        memory_store.upsert([_chunk("текст")], [])


def test_delete_guideline_removes_only_its_chunks(memory_store: ChunkVectorStore) -> None:
    """Перед повторной индексацией удаляются чанки только этого клинрека."""
    own = _chunk("свой чанк")
    other = _chunk("чужой чанк").model_copy(update={"guideline_id": uuid4()})
    memory_store.upsert([own, other], [[0.1] * 8, [0.2] * 8])

    memory_store.delete_guideline(GUIDELINE_ID)

    assert memory_store.get(own.chunk_id) is None
    assert memory_store.get(other.chunk_id) is not None
