"""Проверки эндпоинтов фрагментов и запуска индексации."""

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fakes import FakeEmbedder
from fastapi.testclient import TestClient

from app.clients.vector_store import ChunkVectorStore
from app.config import Settings
from app.main import create_app
from app.runtime import Runtime
from app.schemas.chunk import Chunk, ChunkRect
from app.schemas.guideline import GuidelineStatus


@pytest.fixture
def runtime(
    settings: Settings, fake_embedder: FakeEmbedder, memory_store: ChunkVectorStore
) -> Runtime:
    """Рантайм с подменёнными моделью и хранилищем: сеть и веса не нужны."""
    return Runtime(settings, embedder=fake_embedder, store=memory_store)


@pytest.fixture
def client(runtime: Runtime, settings: Settings) -> Iterator[TestClient]:
    """Клиент приложения с запущенным жизненным циклом."""
    with TestClient(create_app(settings, runtime)) as test_client:
        yield test_client


def _upload(client: TestClient, pdf: Path, title: str = "Клинрек") -> dict:
    """Загрузить настоящий PDF через API."""
    response = client.post(
        "/api/guidelines",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"title": title, "icd_codes": "I10"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk(guideline_id: str, pages: list[int]) -> Chunk:
    """Чанк с прямоугольниками на указанных страницах."""
    rects = [ChunkRect(page=page, bbox=(72.0, 700.0, 500.0, 712.0)) for page in pages]
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=guideline_id,
        guideline_version=1,
        section="2. Диагностика",
        text="Измерение артериального давления на обеих руках.",
        chunk_index=0,
        page=rects[0].page,
        bbox=rects[0].bbox,
        rects=rects,
    )


def test_upload_answers_before_indexing_and_then_becomes_ready(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    """Ответ на загрузку приходит со статусом `uploaded`, индексация идёт после."""
    body = _upload(client, mini_pdf)

    assert body["status"] == "uploaded"

    indexed = client.get(f"/api/guidelines/{body['guideline_id']}").json()
    assert indexed["status"] == GuidelineStatus.READY.value
    assert indexed["chunks_total"] and indexed["chunks_total"] > 0
    assert indexed["chunks_indexed"] == indexed["chunks_total"]
    assert indexed["embedding_model"]
    assert indexed["indexed_at"] is not None


def test_new_fields_are_optional_for_old_manifest(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    """Манифест без полей индексации читается, а новые поля попадают в ответ."""
    body = _upload(client, mini_pdf)
    guideline = runtime.guidelines.get(body["guideline_id"])
    legacy = guideline.model_copy(
        update={
            "chunks_total": None,
            "chunks_indexed": None,
            "embedding_model": None,
            "indexed_at": None,
        }
    )
    runtime.guidelines.save(legacy)

    response = client.get(f"/api/guidelines/{body['guideline_id']}")

    assert response.status_code == 200
    assert response.json()["chunks_total"] is None
    assert response.json()["embedding_model"] is None


def test_chunk_endpoint_returns_text_and_rects(
    client: TestClient, memory_store: ChunkVectorStore, runtime: Runtime, mini_pdf: Path
) -> None:
    """Одно- и многостраничный чанк отдаются с текстом, секцией и прямоугольниками."""
    guideline_id = _upload(client, mini_pdf)["guideline_id"]
    single = _chunk(guideline_id, [5])
    spanning = _chunk(guideline_id, [7, 8])
    memory_store.upsert([single, spanning], [[0.1] * 8, [0.2] * 8])

    first = client.get(f"/api/chunks/{single.chunk_id}")
    second = client.get(f"/api/chunks/{spanning.chunk_id}")

    assert first.status_code == 200
    assert first.json()["text"] == single.text
    assert first.json()["section"] == "2. Диагностика"
    assert [rect["page"] for rect in first.json()["rects"]] == [5]
    assert second.status_code == 200
    assert [rect["page"] for rect in second.json()["rects"]] == [7, 8]
    assert second.json()["page"] == 7
    assert second.json()["bbox"] == second.json()["rects"][0]["bbox"]


def test_unknown_chunk_is_not_found(client: TestClient) -> None:
    """Неизвестный идентификатор фрагмента даёт 404."""
    response = client.get(f"/api/chunks/{uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_index_endpoint_requeues_failed_guideline(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    """Повтор для упавшего клинрека возвращает его в обработку и доводит до `ready`."""
    guideline_id = _upload(client, mini_pdf)["guideline_id"]
    failed = runtime.guidelines.get(guideline_id).model_copy(
        update={"status": GuidelineStatus.FAILED, "error": "падение"}
    )
    runtime.guidelines.save(failed)

    response = client.post(f"/api/guidelines/{guideline_id}/index")

    assert response.status_code == 202
    assert response.json()["status"] == GuidelineStatus.PROCESSING.value
    assert client.get(f"/api/guidelines/{guideline_id}").json()["status"] == "ready"


def test_index_endpoint_conflicts_while_running(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    """Повтор во время идущей индексации отклоняется."""
    guideline_id = _upload(client, mini_pdf)["guideline_id"]
    # Идентификатор из JSON — строка, а набор идущих индексаций хранит UUID
    runtime.indexer._running.add(UUID(guideline_id))
    try:
        response = client.post(f"/api/guidelines/{guideline_id}/index")
    finally:
        runtime.indexer._running.discard(UUID(guideline_id))

    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_index_endpoint_unknown_guideline(client: TestClient) -> None:
    """Повтор для неизвестного клинрека даёт 404."""
    response = client.post(f"/api/guidelines/{uuid4()}/index")

    assert response.status_code == 404


def test_failed_indexing_is_visible_in_guideline(
    client: TestClient, runtime: Runtime, scanned_pdf: Path
) -> None:
    """Отказ индексации виден через API вместе с причиной."""
    body = _upload(client, scanned_pdf)

    indexed = client.get(f"/api/guidelines/{body['guideline_id']}").json()

    assert indexed["status"] == GuidelineStatus.FAILED.value
    assert "текстового слоя" in indexed["error"]
    assert client.get(f"/api/guidelines/{body['guideline_id']}/file").status_code == 200
