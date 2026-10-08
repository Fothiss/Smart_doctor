"""Общие фикстуры тестов."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from app.services.guidelines import GuidelineService

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

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
