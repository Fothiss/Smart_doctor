"""Проверки удаления клинрека: сервис, рантайм и HTTP-контракт."""

from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fakes import FakeChunkStore, FakeEmbedder
from fastapi.testclient import TestClient

from app.clients.vector_store import ChunkVectorStore, VectorStoreError
from app.config import Settings
from app.main import create_app
from app.runtime import Runtime
from app.schemas.chunk import Chunk
from app.services.guidelines import GuidelineNotFoundError, GuidelineService
from app.services.indexing import IndexingInProgressError

ChunkStream = Callable[..., AsyncIterator[bytes]]


@pytest.fixture
def store() -> FakeChunkStore:
    """Хранилище-шпион: помнит, какие клинреки у него просили удалить."""
    return FakeChunkStore()


@pytest.fixture
def runtime(settings: Settings, fake_embedder: FakeEmbedder, store: FakeChunkStore) -> Runtime:
    """Рантайм с подменёнными моделью и хранилищем."""
    return Runtime(settings, embedder=fake_embedder, store=store)


async def test_service_delete_removes_directory_and_manifest(
    service: GuidelineService,
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"])
    directory = guidelines_dir / str(guideline.guideline_id)
    assert (directory / "original.pdf").is_file()

    service.delete(guideline.guideline_id)

    assert not directory.exists()
    with pytest.raises(GuidelineNotFoundError):
        service.get(guideline.guideline_id)


async def test_service_delete_unknown_guideline_is_not_found(
    service: GuidelineService,
) -> None:
    with pytest.raises(GuidelineNotFoundError):
        service.delete(uuid4())


async def test_runtime_delete_removes_chunks_before_files(
    runtime: Runtime,
    store: FakeChunkStore,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await runtime.guidelines.create(
        stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"]
    )

    runtime.delete_guideline(guideline.guideline_id)

    assert store.deleted == [guideline.guideline_id]
    with pytest.raises(GuidelineNotFoundError):
        runtime.guidelines.get(guideline.guideline_id)


async def test_runtime_delete_keeps_files_when_store_is_unavailable(
    settings: Settings,
    fake_embedder: FakeEmbedder,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    store = FakeChunkStore(fail=True)
    runtime = Runtime(settings, embedder=fake_embedder, store=store)
    guideline = await runtime.guidelines.create(
        stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"]
    )

    with pytest.raises(VectorStoreError):
        runtime.delete_guideline(guideline.guideline_id)

    # Клинрек остаётся целым: манифест читается, файл PDF на месте
    assert runtime.guidelines.get(guideline.guideline_id) == guideline
    assert runtime.guidelines.get_pdf(guideline.guideline_id)[1].is_file()
    assert store.deleted == []


async def test_runtime_delete_rejects_running_indexing(
    runtime: Runtime,
    store: FakeChunkStore,
    stream: ChunkStream,
    pdf_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guideline = await runtime.guidelines.create(
        stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"]
    )
    monkeypatch.setattr(runtime, "is_indexing", lambda _: True)

    with pytest.raises(IndexingInProgressError):
        runtime.delete_guideline(guideline.guideline_id)

    assert store.deleted == []
    assert runtime.guidelines.get(guideline.guideline_id) == guideline


@pytest.fixture
def api_runtime(
    settings: Settings, fake_embedder: FakeEmbedder, memory_store: ChunkVectorStore
) -> Runtime:
    """Рантайм с настоящим (в памяти) векторным хранилищем для проверок API."""
    return Runtime(settings, embedder=fake_embedder, store=memory_store)


@pytest.fixture
def client(api_runtime: Runtime, settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, api_runtime)) as test_client:
        yield test_client


def _upload(client: TestClient, pdf: Path, icd_codes: str = "I10") -> dict:
    """Загрузить настоящий PDF через API и вернуть тело ответа."""
    response = client.post(
        "/api/guidelines",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"title": "Гипертензия", "icd_codes": icd_codes},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk(guideline_id: str) -> Chunk:
    """Фрагмент клинрека для проверки, что удаление дошло до хранилища."""
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=UUID(guideline_id),
        guideline_version=1,
        section="2. Диагностика",
        text="Измерение артериального давления на обеих руках.",
        chunk_index=0,
        page=1,
        bbox=None,
        rects=[],
    )


def test_api_delete_removes_guideline_and_its_chunks(
    client: TestClient, api_runtime: Runtime, mini_pdf: Path
) -> None:
    guideline_id = _upload(client, mini_pdf)["guideline_id"]
    chunk = _chunk(guideline_id)
    api_runtime.store.upsert([chunk], [[0.0] * 8])
    assert api_runtime.store.get(chunk.chunk_id) is not None

    response = client.delete(f"/api/guidelines/{guideline_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert api_runtime.store.get(chunk.chunk_id) is None
    assert client.get(f"/api/guidelines/{guideline_id}").status_code == 404
    assert client.get(f"/api/guidelines/{guideline_id}/file").status_code == 404
    assert [item["guideline_id"] for item in client.get("/api/guidelines").json()] != [
        guideline_id
    ]


def test_api_delete_unknown_guideline_is_not_found(client: TestClient) -> None:
    response = client.delete(f"/api/guidelines/{uuid4()}")

    assert response.status_code == 404


def test_api_delete_rejects_running_indexing(
    client: TestClient, api_runtime: Runtime, mini_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guideline_id = _upload(client, mini_pdf)["guideline_id"]
    monkeypatch.setattr(api_runtime, "is_indexing", lambda _: True)

    response = client.delete(f"/api/guidelines/{guideline_id}")

    assert response.status_code == 409
    assert client.get(f"/api/guidelines/{guideline_id}").status_code == 200


def test_api_delete_keeps_guideline_when_store_is_unavailable(
    client: TestClient, api_runtime: Runtime, mini_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guideline_id = _upload(client, mini_pdf)["guideline_id"]

    def broken(_: UUID) -> None:
        raise VectorStoreError("vector store is unavailable")

    monkeypatch.setattr(api_runtime.store, "delete_guideline", broken)

    response = client.delete(f"/api/guidelines/{guideline_id}")

    assert response.status_code == 503
    assert client.get(f"/api/guidelines/{guideline_id}").status_code == 200
