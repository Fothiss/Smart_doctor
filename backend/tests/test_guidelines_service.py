"""Проверки сервиса клинреков: приём, чтение, список, оригинал PDF."""

import hashlib
import json
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
    icd_codes: list[str] | None = None,
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
        icd_codes=icd_codes or [],
    )
    (directory / "meta.json").write_text(guideline.model_dump_json(), encoding="utf-8")
    return guideline


async def test_create_stores_pdf_and_manifest(
    service: GuidelineService,
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(
        stream(pdf_bytes), "klinrek.pdf", "Гипертензия", icd_codes=["i10", "I10"]
    )

    stored = guidelines_dir / str(guideline.guideline_id)
    assert (stored / "original.pdf").read_bytes() == pdf_bytes
    assert Guideline.model_validate_json((stored / "meta.json").read_text("utf-8")) == guideline
    assert guideline.status is GuidelineStatus.UPLOADED
    assert guideline.version == 1
    assert guideline.filename == "klinrek.pdf"
    assert guideline.title == "Гипертензия"
    assert guideline.size_bytes == len(pdf_bytes)
    assert guideline.sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    # Коды нормализованы и без повторов: регистр поднят, дубликат отброшен
    assert guideline.icd_codes == ["I10"]


async def test_create_requires_icd_codes(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    with pytest.raises(InvalidGuidelineError, match="at least one ICD code is required"):
        await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=[])


async def test_create_rejects_invalid_icd_code(
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)

    with pytest.raises(InvalidGuidelineError, match="invalid ICD code"):
        await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10", "гипертензия"])

    # Непригодный код отказывает до записи файла: каталог клинрека не появляется
    assert not guidelines_dir.exists()


async def test_create_uses_file_stem_as_title(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(stream(pdf_bytes), "КР62_3.pdf", icd_codes=["I10"])

    assert guideline.title == "КР62_3"


async def test_create_creates_storage_directory_on_demand(
    tmp_path: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guidelines_dir = tmp_path / "nested" / "guidelines"
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024 * 1024)

    guideline = await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"])

    assert (guidelines_dir / str(guideline.guideline_id) / "original.pdf").is_file()


async def test_create_strips_directory_from_filename(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    guideline = await service.create(
        stream(pdf_bytes), r"..\..\etc\passwd.pdf", icd_codes=["I10"]
    )

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
        await service.create(stream(pdf_bytes), filename, icd_codes=["I10"])


async def test_create_rejects_non_pdf_content(
    service: GuidelineService,
    guidelines_dir: Path,
    stream: ChunkStream,
) -> None:
    with pytest.raises(InvalidGuidelineError, match="file is not a PDF"):
        await service.create(stream(b"not a pdf at all"), "klinrek.pdf", icd_codes=["I10"])

    assert list(guidelines_dir.iterdir()) == []


async def test_create_rejects_empty_file(
    service: GuidelineService,
    stream: ChunkStream,
) -> None:
    with pytest.raises(InvalidGuidelineError, match="file is empty"):
        await service.create(stream(), "klinrek.pdf", icd_codes=["I10"])


async def test_create_rejects_oversized_file(
    guidelines_dir: Path,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=16)

    with pytest.raises(GuidelineTooLargeError, match="file exceeds"):
        await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"])

    assert list(guidelines_dir.iterdir()) == []


async def test_create_detects_duplicate(
    service: GuidelineService,
    stream: ChunkStream,
    pdf_bytes: bytes,
) -> None:
    first = await service.create(stream(pdf_bytes), "klinrek.pdf", icd_codes=["I10"])

    with pytest.raises(DuplicateGuidelineError) as excinfo:
        await service.create(stream(pdf_bytes), "copy.pdf", icd_codes=["I10"])

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


def test_manifest_without_icd_codes_reads_with_empty_list(
    guidelines_dir: Path, pdf_bytes: bytes
) -> None:
    """Манифест, записанный до появления кодов, не считается битым."""
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_manifest(guidelines_dir, pdf_bytes, created_at=datetime.now(UTC))
    meta_path = guidelines_dir / str(guideline.guideline_id) / "meta.json"
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload.pop("icd_codes")
    meta_path.write_text(json.dumps(payload), encoding="utf-8")

    assert service.get(guideline.guideline_id).icd_codes == []


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


def test_list_filters_by_icd(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    hypertension = _write_manifest(
        guidelines_dir,
        pdf_bytes,
        created_at=datetime.now(UTC),
        icd_codes=["I10", "I15"],
    )
    _write_manifest(
        guidelines_dir,
        pdf_bytes,
        created_at=datetime.now(UTC),
        icd_codes=["J06"],
    )

    assert [g.guideline_id for g in service.list(icd="I10")] == [hypertension.guideline_id]
    # Уточнение кода совпадает с клинреком, который покрывает его целиком
    assert [g.guideline_id for g in service.list(icd="I15.9")] == [hypertension.guideline_id]
    assert service.list(icd="J06") != []
    assert service.list(icd="K35") == []


def test_list_filters_by_status_and_icd_together(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    _write_manifest(
        guidelines_dir,
        pdf_bytes,
        created_at=datetime.now(UTC),
        status=GuidelineStatus.UPLOADED,
        icd_codes=["I10"],
    )
    ready = _write_manifest(
        guidelines_dir,
        pdf_bytes,
        created_at=datetime.now(UTC),
        status=GuidelineStatus.READY,
        icd_codes=["I10"],
    )

    filtered = service.list(status=GuidelineStatus.READY, icd="I10")

    assert [g.guideline_id for g in filtered] == [ready.guideline_id]


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
