"""Проверки HTTP-контракта валидации черновика протокола."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fakes import FakeEmbedder
from fastapi.testclient import TestClient

from app.clients.vector_store import ChunkVectorStore
from app.config import Settings
from app.main import create_app
from app.runtime import Runtime
from app.schemas.guideline import GuidelineStatus

PROTOCOL_PATH = "/api/protocols/validate"


def _form(**overrides: object) -> dict:
    """Тело формы протокола с возможностью заменить отдельные поля."""
    form: dict[str, object] = {
        "complaints": "Головная боль, головокружение",
        "diagnosis": {"code": "I10", "name": "Гипертензия"},
        "diagnosis_description": "АГ 2 ст., риск 3",
        "prescriptions": [
            {"kind": "drug", "name": "Амлодипин", "dose": "5 мг", "frequency": "1 раз в сутки"},
            {"kind": "procedure", "name": "ЭКГ"},
        ],
    }
    form.update(overrides)
    return form


def _body(guideline_id: str, form: dict | None = None) -> dict:
    return {"guideline_id": guideline_id, "form": form or _form()}


@pytest.fixture
def runtime(
    settings: Settings, fake_embedder: FakeEmbedder, memory_store: ChunkVectorStore
) -> Runtime:
    """Рантайм с подменёнными моделью и хранилищем: сеть и веса не нужны."""
    return Runtime(settings, embedder=fake_embedder, store=memory_store)


@pytest.fixture
def client(runtime: Runtime, settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, runtime)) as test_client:
        yield test_client


def _upload(client: TestClient, pdf: Path, icd_codes: str = "I10") -> dict:
    """Загрузить PDF и дождаться индексации: для проверок нужен готовый клинрек."""
    response = client.post(
        "/api/guidelines",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"title": "Гипертензия", "icd_codes": icd_codes},
    )
    assert response.status_code == 201, response.text
    guideline_id = response.json()["guideline_id"]
    guideline = client.get(f"/api/guidelines/{guideline_id}").json()
    assert guideline["status"] == GuidelineStatus.READY.value, guideline
    return guideline


def test_validate_returns_draft_and_statements(client: TestClient, mini_pdf: Path) -> None:
    guideline = _upload(client, mini_pdf)

    response = client.post(PROTOCOL_PATH, json=_body(guideline["guideline_id"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["guideline"]["guideline_id"] == guideline["guideline_id"]
    assert body["guideline"]["icd_codes"] == ["I10"]
    assert body["form"]["diagnosis"]["code"] == "I10"
    assert body["statements"] == [
        "Жалобы: Головная боль, головокружение",
        "Диагноз: I10 — Гипертензия",
        "Описание диагноза: АГ 2 ст., риск 3",
        "Назначение: Амлодипин, 5 мг, 1 раз в сутки",
        "Процедура: ЭКГ",
    ]


def test_validate_does_not_store_anything(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    guideline = _upload(client, mini_pdf)
    before = sorted(path.name for path in runtime.settings.backend.storage_dir.glob("*/*"))

    response = client.post(PROTOCOL_PATH, json=_body(guideline["guideline_id"]))

    assert response.status_code == 200
    after = sorted(path.name for path in runtime.settings.backend.storage_dir.glob("*/*"))
    assert after == before


def test_validate_rejects_empty_required_field(client: TestClient, mini_pdf: Path) -> None:
    guideline = _upload(client, mini_pdf)

    response = client.post(
        PROTOCOL_PATH, json=_body(guideline["guideline_id"], _form(complaints="  "))
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("complaints:")


def test_validate_rejects_bad_icd_code(client: TestClient, mini_pdf: Path) -> None:
    guideline = _upload(client, mini_pdf)
    form = _form(diagnosis={"code": "гипертензия", "name": "Гипертензия"})

    response = client.post(PROTOCOL_PATH, json=_body(guideline["guideline_id"], form))

    assert response.status_code == 400
    assert response.json()["detail"].startswith("diagnosis.code:")


def test_validate_rejects_unknown_guideline(client: TestClient) -> None:
    response = client.post(PROTOCOL_PATH, json=_body(str(uuid4())))

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_validate_rejects_guideline_that_is_not_ready(
    client: TestClient, runtime: Runtime, mini_pdf: Path
) -> None:
    guideline = _upload(client, mini_pdf)
    stored = runtime.guidelines.get(guideline["guideline_id"])
    runtime.guidelines.save(stored.model_copy(update={"status": GuidelineStatus.PROCESSING}))

    response = client.post(PROTOCOL_PATH, json=_body(guideline["guideline_id"]))

    assert response.status_code == 409
    assert "processing" in response.json()["detail"]
