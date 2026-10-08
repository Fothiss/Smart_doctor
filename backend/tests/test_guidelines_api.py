"""Проверки HTTP-контракта клинреков."""

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers.guidelines import get_guideline_service
from app.services.guidelines import GuidelineService


def _app_with(service: GuidelineService) -> FastAPI:
    """Приложение с подменённым сервисом клинреков (DI вместо глобальных настроек)."""
    app = create_app()
    app.dependency_overrides[get_guideline_service] = lambda: service
    return app


def _upload(
    client: TestClient,
    pdf: bytes,
    filename: str = "klinrek.pdf",
    **form: str,
) -> object:
    """Отправить PDF на загрузку как multipart/form-data."""
    return client.post(
        "/api/guidelines",
        files={"file": (filename, pdf, "application/pdf")},
        data=form,
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


def test_list_returns_uploaded_guideline(client: TestClient, pdf_bytes: bytes) -> None:
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get("/api/guidelines")

    assert response.status_code == 200
    assert [item["guideline_id"] for item in response.json()] == [uploaded["guideline_id"]]


def test_list_filters_by_status(client: TestClient, pdf_bytes: bytes) -> None:
    _upload(client, pdf_bytes)

    assert client.get("/api/guidelines", params={"status": "ready"}).json() == []
    assert len(client.get("/api/guidelines", params={"status": "uploaded"}).json()) == 1


def test_list_rejects_non_positive_limit(client: TestClient) -> None:
    response = client.get("/api/guidelines", params={"limit": 0})

    assert response.status_code == 422


def test_get_guideline_by_id(client: TestClient, pdf_bytes: bytes) -> None:
    uploaded = _upload(client, pdf_bytes).json()

    response = client.get(f"/api/guidelines/{uploaded['guideline_id']}")

    assert response.status_code == 200
    assert response.json() == uploaded


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
