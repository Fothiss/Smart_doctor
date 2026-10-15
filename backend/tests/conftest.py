"""Общие фикстуры тестов."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from fakes import FakeEmbedder
from qdrant_client import QdrantClient

from app.clients.vector_store import ChunkVectorStore
from app.config import (
    BackendSettings,
    DatabaseSettings,
    EmbeddingSettings,
    LLMSettings,
    QdrantMode,
    Settings,
)
from app.services.guidelines import GuidelineService

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

DATA_DIR = Path(__file__).resolve().parent / "data"
"""Каталог с настоящими PDF для тестов извлечения и чанкинга."""

FAKE_DIMENSION = 8
"""Размерность подменённого эмбеддера: настоящие 1024 в тестах не нужны."""

ChunkStream = Callable[..., AsyncIterator[bytes]]


@pytest.fixture
def pdf_bytes() -> bytes:
    """Минимальный файл с сигнатурой PDF."""
    return PDF_BYTES


@pytest.fixture
def guidelines_dir(tmp_path: Path) -> Path:
    """Пустой каталог хранилища клинреков."""
    return tmp_path / "guidelines"


@pytest.fixture
def service(guidelines_dir: Path) -> GuidelineService:
    """Сервис клинреков с лимитом загрузки 1 МБ."""
    return GuidelineService(guidelines_dir, max_upload_size_bytes=1024 * 1024)


@pytest.fixture
def stream() -> Callable[..., AsyncIterator[bytes]]:
    """Собрать асинхронный поток чанков из переданных кусков."""

    def _stream(*parts: bytes) -> AsyncIterator[bytes]:
        async def _generate() -> AsyncIterator[bytes]:
            for part in parts:
                yield part

        return _generate()

    return _stream


@pytest.fixture(scope="session")
def mini_pdf() -> Path:
    """Настоящий PDF из четырёх страниц: титул, оглавление, текст, поворот."""
    return DATA_DIR / "mini.pdf"


@pytest.fixture(scope="session")
def scanned_pdf() -> Path:
    """PDF без текстового слоя: две страницы без символов."""
    return DATA_DIR / "scanned.pdf"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Настройки, изолированные в каталоге теста."""
    return Settings(
        backend=BackendSettings(storage_dir=tmp_path / "storage", max_upload_size_mb=5),
        database=DatabaseSettings(
            qdrant_mode=QdrantMode.LOCAL, qdrant_local_path=tmp_path / "qdrant"
        ),
        llm=LLMSettings(),
        embedding=EmbeddingSettings(
            dimension=FAKE_DIMENSION, ml_models_dir=tmp_path / "models"
        ),
    )


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """Подменённый эмбеддер фиксированной размерности."""
    return FakeEmbedder(dimension=FAKE_DIMENSION)


@pytest.fixture
def memory_store(fake_embedder: FakeEmbedder) -> ChunkVectorStore:
    """Векторное хранилище в памяти: каталог не занимается и блокировка не мешает."""
    store = ChunkVectorStore(
        client=QdrantClient(":memory:"),
        collection=f"test_chunks__{fake_embedder.dimension}",
        dimension=fake_embedder.dimension,
    )
    store.ensure_collection()
    return store
