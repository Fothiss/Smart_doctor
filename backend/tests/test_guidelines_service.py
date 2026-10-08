"""Проверки сервиса клинреков: приём, чтение, список, оригинал PDF."""

import hashlib
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.guidelines import (
    DuplicateGuidelineError,
    GuidelineNotFoundError,
    GuidelineService,
    GuidelineTooLargeError,
    InvalidGuidelineError,
    safe_filename,
)

ChunkStream = Callable[..., AsyncIterator[bytes]]


def _write_manifest(
    guidelines_dir: Path,
    pdf_bytes: bytes,
    *,
    created_at: datetime,
    status: GuidelineStatus = GuidelineStatus.READY,
    with_pdf: bool = True,
) -> Guideline:
    """Разложить клинрек в хранилище вручную — для проверок чтения и списка."""
    guideline_id = uuid4()
    directory = guidelines_dir / str(guideline_id)
    directory.mkdir(parents=True)
    if with_pdf:
        (directory / "original.pdf").write_bytes(pdf_bytes)
    guideline = Guideline(
        guideline_id=guideline_id,
        version=1,
        title="Гипертензия",
        filename="klinrek.pdf",
        size_bytes=len(pdf_bytes),
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        status=status,
        created_at=created_at,
    )
    (directory / "meta.json").write_text(guideline.model_dump_json(), encoding="utf-8")
    return guideline


async def test_create_stores_pdf_and_manifest(
    service: GuidelineService,
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(stream(pdf_bytes), "klinrek.pdf", "Гипертензия")

    stored = guidelines_dir / str(guideline.guideline_id)
    assert (stored / "original.pdf").read_bytes() == pdf_bytes
    assert Guideline.model_validate_json((stored / "meta.json").read_text("utf-8")) == guideline
    assert guideline.status is GuidelineStatus.UPLOADED
    assert guideline.version == 1
    assert guideline.filename == "klinrek.pdf"
    assert guideline.title == "Гипертензия"
    assert guideline.size_bytes == len(pdf_bytes)
    assert guideline.sha256 == hashlib.sha256(pdf_bytes).hexdigest()


async def test_create_uses_file_stem_as_title(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(stream(pdf_bytes), "КР62_3.pdf")

    assert guideline.title == "КР62_3"


async def test_create_creates_storage_directory_on_demand(
    tmp_path: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guidelines_dir = tmp_path / "nested" / "guidelines"
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024 * 1024)

    guideline = await service.create(stream(pdf_bytes), "klinrek.pdf")

    assert (guidelines_dir / str(guideline.guideline_id) / "original.pdf").is_file()


async def test_create_strips_directory_from_filename(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(stream(pdf_bytes), r"..\..\etc\passwd.pdf")

    assert guideline.filename == "passwd.pdf"


@pytest.mark.parametrize(
    ("filename", "message"),
    [
        ("", "file name is required"),
        ("   ", "file name is required"),
        ("klinrek.txt", "only PDF files are supported"),
    ],
)
async def test_create_rejects_bad_filename(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
    filename: str,
    message: str,
) -> None:
    with pytest.raises(InvalidGuidelineError, match=message):
        await service.create(stream(pdf_bytes), filename)


async def test_create_rejects_non_pdf_content(
    service: GuidelineService,
    guidelines_dir: Path,
    stream: ChunkStream,
) -> None:
    with pytest.raises(InvalidGuidelineError, match="file is not a PDF"):
        await service.create(stream(b"not a pdf at all"), "klinrek.pdf")

    assert list(guidelines_dir.iterdir()) == []


async def test_create_rejects_empty_file(
    service: GuidelineService,
    stream: ChunkStream,
) -> None:
    with pytest.raises(InvalidGuidelineError, match="file is empty"):
        await service.create(stream(), "klinrek.pdf")


async def test_create_rejects_oversized_file(
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=16)

    with pytest.raises(GuidelineTooLargeError, match="file exceeds"):
        await service.create(stream(pdf_bytes), "klinrek.pdf")

    assert list(guidelines_dir.iterdir()) == []


async def test_create_detects_duplicate(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    first = await service.create(stream(pdf_bytes), "klinrek.pdf")

    with pytest.raises(DuplicateGuidelineError) as excinfo:
        await service.create(stream(pdf_bytes), "copy.pdf")

    assert excinfo.value.guideline.guideline_id == first.guideline_id


def test_get_returns_manifest(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    expected = _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))

    assert service.get(expected.guideline_id) == expected


def test_get_missing_raises_not_found(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline_id = uuid4()

    with pytest.raises(GuidelineNotFoundError) as excinfo:
        service.get(guideline_id)

    assert excinfo.value.guideline_id == guideline_id
    assert excinfo.value.version is None


def test_get_version_mismatch_raises_not_found(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))

    assert service.get(guideline.guideline_id, version=1) == guideline
    with pytest.raises(GuidelineNotFoundError) as excinfo:
        service.get(guideline.guideline_id, version=2)

    assert excinfo.value.version == 2


def test_get_broken_manifest_is_not_found(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline_id = uuid4()
    directory = guidelines_dir / str(guideline_id)
    directory.mkdir(parents=True)
    (directory / "meta.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(GuidelineNotFoundError):
        service.get(guideline_id)


def test_list_sorts_newest_first_and_paginates(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    now = datetime.now(UTC)
    oldest = _write_manifest(guidelines_dir, pdf_bytes, created_at=now - timedelta(hours=2))
    middle = _write_manifest(guidelines_dir, pdf_bytes, created_at=now - timedelta(hours=1))
    newest = _write_manifest(guidelines_dir, pdf_bytes, created_at=now)

    assert [g.guideline_id for g in service.list()] == [
        newest.guideline_id,
        middle.guideline_id,
        oldest.guideline_id,
    ]
    assert [g.guideline_id for g in service.list(limit=1, offset=1)] == [middle.guideline_id]


def test_list_filters_by_status(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    uploaded = _write_manifest(
        guidelines_dir, pdf_bytes, created_at=datetime.now(UTC), status=GuidelineStatus.UPLOADED
    )
    _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))

    assert [g.guideline_id for g in service.list(status=GuidelineStatus.UPLOADED)] == [
        uploaded.guideline_id
    ]


def test_list_skips_broken_manifests(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    expected = _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))
    broken = guidelines_dir / str(uuid4())
    broken.mkdir(parents=True)
    (broken / "meta.json").write_text("{}", encoding="utf-8")

    assert [g.guideline_id for g in service.list()] == [expected.guideline_id]


def test_get_pdf_returns_stored_file(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))

    stored_guideline, pdf_path = service.get_pdf(guideline.guideline_id)

    assert stored_guideline == guideline
    assert pdf_path.read_bytes() == pdf_bytes


def test_get_pdf_without_file_is_not_found(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_manifest(
        guidelines_dir, pdf_bytes, created_at=datetime.now(UTC), with_pdf=False
    )

    with pytest.raises(GuidelineNotFoundError):
        service.get_pdf(guideline.guideline_id)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"C:\docs\klinrek.pdf", "klinrek.pdf"),
        ("/tmp/docs/klinrek.pdf", "klinrek.pdf"),
        ("klinrek.pdf", "klinrek.pdf"),
        ("  klinrek.pdf  ", "klinrek.pdf"),
        ("", ""),
    ],
)
def test_safe_filename_ignores_any_separator(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected
