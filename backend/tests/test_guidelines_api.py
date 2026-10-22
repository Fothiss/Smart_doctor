"""Проверки HTTP-контракта клинреков."""

import hashlib
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.main import create_app
from app.routers.guidelines import get_guideline_service
from app.services.guidelines import GuidelineService

ICD_CODES: tuple[str, ...] = ("I10",)
"""Коды МКБ, с которыми загружается клинрек по умолчанию в проверках."""


def _app_with(service: GuidelineService) -> FastAPI:
    """Приложение с подменённым сервисом клинреков (DI вместо глобальных настроек)."""
    app = create_app()
    app.dependency_overrides[get_guideline_service] = lambda: service
    return app


def _upload(
    client: TestClient,
    pdf: bytes,
    filename: str = "klinrek.pdf",
    icd_codes: Sequence[str] = ICD_CODES,
    **form: str,
) -> Response:
    """Отправить PDF на загрузку как multipart/form-data.

    Повторяющееся поле ``icd_codes`` собирается из переданного списка: FastAPI
    принимает ``list[str]`` только из повторяющихся полей формы.
    """
    data: dict[str, object] = dict(form)
    if icd_codes:
        data["icd_codes"] = list(icd_codes)
    return client.post(
        "/api/guidelines",
        files={"file": (filename, pdf, "application/pdf")},
        data=data,
    )


@pytest.fixture
def client(service: GuidelineService) -> Iterator[TestClient]:
    with TestClient(_app_with(service)) as test_client:
        yield test_client


def test_health_is_alive(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_upload_returns_created_guideline(client: TestClient, pdf_bytes: bytes) -> None:
    response = _upload(client, pdf_bytes, title="Гипертензия")

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Гипертензия"
    assert body["filename"] == "klinrek.pdf"
    assert body["status"] == "uploaded"
    assert body["version"] == 1
    assert body["size_bytes"] == len(pdf_bytes)
    assert body["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert body["error"] is None


def test_upload_rejects_non_pdf_extension(client: TestClient, pdf_bytes: bytes) -> None:
    response = _upload(client, pdf_bytes, filename="klinrek.txt")

    assert response.status_code == 400
    assert response.json()["detail"] == "only PDF files are supported"


def test_upload_rejects_non_pdf_content(client: TestClient) -> None:
    response = _upload(client, b"not a pdf at all")

    assert response.status_code == 400
    assert response.json()["detail"] == "file is not a PDF"


def test_upload_rejects_duplicate(client: TestClient, pdf_bytes: bytes) -> None:
    first = _upload(client, pdf_bytes)

    response = _upload(client, pdf_bytes)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "guideline with the same content already exists"
    assert detail["guideline_id"] == first.json()["guideline_id"]


def test_upload_rejects_oversized_file(guidelines_dir: Path, pdf_bytes: bytes) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=16)

    with TestClient(_app_with(service)) as client:
        response = _upload(client, pdf_bytes)

    assert response.status_code == 413
    assert "file exceeds" in response.json()["detail"]


def test_upload_stores_normalized_icd_codes(client: TestClient, pdf_bytes: bytes) -> None:
    response = _upload(client, pdf_bytes, icd_codes=["i10", "I10.1", "I10"])

    assert response.status_code == 201
    assert response.json()["icd_codes"] == ["I10", "I10.1"]


def test_upload_rejects_missing_icd_codes(client: TestClient, pdf_bytes: bytes) -> None:
    response = _upload(client, pdf_bytes, icd_codes=())

    assert response.status_code == 400
    assert response.json()["detail"] == "at least one ICD code is required"


def test_upload_rejects_invalid_icd_code(client: TestClient, pdf_bytes: bytes) -> None:
    response = _upload(client, pdf_bytes, icd_codes=["гипертензия"])

    assert response.status_code == 400
    assert "invalid ICD code" in response.json()["detail"]


def test_list_returns_uploaded_guideline(client: TestClient, pdf_bytes: bytes) -> None:
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get("/api/guidelines")

    assert response.status_code == 200
    assert [item["guideline_id"] for item in response.json()] == [uploaded["guideline_id"]]


def test_list_filters_by_status(client: TestClient, pdf_bytes: bytes) -> None:
    _upload(client, pdf_bytes)

    assert client.get("/api/guidelines", params={"status": "ready"}).json() == []
    # После загрузки запускается индексация, и на непригодном PDF она даёт отказ
    assert client.get("/api/guidelines", params={"status": "failed"}).json() != []
    assert client.get("/api/guidelines", params={"status": "uploaded"}).json() == []


def test_list_filters_by_icd(client: TestClient, pdf_bytes: bytes) -> None:
    hypertension = _upload(client, pdf_bytes, icd_codes=["I10", "I15"]).json()
    _upload(client, pdf_bytes + b"\n", icd_codes=["J06"])

    # Регистр кода в фильтре не важен: код нормализуется
    hypertension_only = client.get("/api/guidelines", params={"icd": "i10"}).json()
    assert [item["guideline_id"] for item in hypertension_only] == [hypertension["guideline_id"]]

    # Уточнение кода совпадает с клинреком, который покрывает его целиком
    refined = client.get("/api/guidelines", params={"icd": "I15.9"}).json()
    assert [item["guideline_id"] for item in refined] == [hypertension["guideline_id"]]

    assert client.get("/api/guidelines", params={"icd": "K35"}).json() == []


def test_list_rejects_invalid_icd_filter(client: TestClient) -> None:
    response = client.get("/api/guidelines", params={"icd": "I1"})

    assert response.status_code == 422
    assert "invalid ICD code" in response.json()["detail"]


def test_list_filters_by_status_and_icd_together(client: TestClient, pdf_bytes: bytes) -> None:
    _upload(client, pdf_bytes, icd_codes=["I10"])

    # Индексация непригодного PDF завершается отказом, поэтому в `ready` ничего нет
    assert client.get("/api/guidelines", params={"icd": "I10", "status": "ready"}).json() == []
    failed = client.get("/api/guidelines", params={"icd": "I10", "status": "failed"}).json()
    assert len(failed) == 1
    assert failed[0]["icd_codes"] == ["I10"]


def test_list_rejects_non_positive_limit(client: TestClient) -> None:
    response = client.get("/api/guidelines", params={"limit": 0})

    assert response.status_code == 422


def test_get_guideline_by_id(client: TestClient, pdf_bytes: bytes) -> None:
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get(f"/api/guidelines/{uploaded['guideline_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["guideline_id"] == uploaded["guideline_id"]
    assert body["sha256"] == uploaded["sha256"]
    # Индексация непригодного PDF завершается отказом, поэтому статус отличается
    # от того, что вернула загрузка: она отвечает до начала индексации
    assert body["status"] == "failed"
    assert body["error"]


def test_get_unknown_guideline_is_not_found(client: TestClient) -> None:
    response = client.get("/api/guidelines/2f1a6d3c-0000-4000-8000-000000000000")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_file_returns_original_pdf(client: TestClient, pdf_bytes: bytes) -> None:
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get(f"/api/guidelines/{uploaded['guideline_id']}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="klinrek.pdf"'
    assert response.content == pdf_bytes


def test_file_supports_range_requests(client: TestClient, pdf_bytes: bytes) -> None:
    """PDF.js докачивает страницы частями — FileResponse должен отдавать 206."""
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get(
        f"/api/guidelines/{uploaded['guideline_id']}/file",
        headers={"Range": "bytes=0-7"},
    )

    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 0-7/{len(pdf_bytes)}"
    assert response.content == pdf_bytes[:8]


def test_file_unknown_guideline_is_not_found(client: TestClient) -> None:
    response = client.get("/api/guidelines/2f1a6d3c-0000-4000-8000-000000000000/file")

    assert response.status_code == 404
