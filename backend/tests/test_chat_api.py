"""Проверки HTTP-контракта чата: коды ответов и форма ответа."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fakes import FakeEmbedder, FakeLLM
from fastapi.testclient import TestClient

from app.clients.llm import LLMError
from app.clients.vector_store import ChunkVectorStore, ScoredChunk, VectorStoreError
from app.config import Settings
from app.main import create_app
from app.runtime import Runtime
from app.schemas.chunk import Chunk, ChunkRect
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.prompts.chat import LlmAnswer, LlmCitation
from app.services.prompts.rewrite import SearchQuery

ASK_PATH = "/api/chat/ask"
CHUNK_TEXT = "Целевой уровень АД — ниже 140/90 мм рт. ст. При хорошей переносимости — 130/80."
QUESTION = "до какого давления снижать пациенту 60 лет?"


def _manifest(settings: Settings, status: GuidelineStatus = GuidelineStatus.READY) -> Guideline:
    """Записать готовый клинрек напрямую в хранилище: PDF и индексация не нужны."""
    guideline = Guideline(
        guideline_id=uuid4(),
        version=1,
        title="Гипертензия",
        filename="kr.pdf",
        size_bytes=1024,
        sha256="1" * 64,
        status=status,
        created_at=datetime.now(UTC),
    )
    target = settings.backend.guidelines_dir / str(guideline.guideline_id)
    target.mkdir(parents=True, exist_ok=True)
    (target / "meta.json").write_text(guideline.model_dump_json(), encoding="utf-8")
    return guideline


def _chunk(guideline_id: UUID) -> Chunk:
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=guideline_id,
        guideline_version=1,
        section="3.2. Целевые уровни",
        text=CHUNK_TEXT,
        chunk_index=0,
        page=9,
        bbox=(0.0, 0.0, 1.0, 1.0),
        rects=[ChunkRect(page=9, bbox=(0.0, 0.0, 1.0, 1.0))],
    )


class _RaisingStore:
    """Хранилище, которое не может искать: проверка ответа `503`."""

    def search(self, vector: object, guideline_ids: object, limit: int) -> list[ScoredChunk]:
        raise VectorStoreError("vector store is unavailable")

    def close(self) -> None:
        """Закрывать нечего: подмена живёт в памяти теста."""
        return None


def _thesis() -> SearchQuery:
    return SearchQuery(
        expression="целевой уровень артериального давления у пациента 60 лет",
        constraints=[],
        is_followup=False,
    )


def _answer() -> LlmAnswer:
    return LlmAnswer(
        answer="Снижать до 140/90 [1].",
        citations=[LlmCitation(n=1, quote="ниже 140/90 мм рт. ст.")],
    )


@pytest.fixture
def client_factory(settings: Settings, fake_embedder: FakeEmbedder):
    """Собрать клиент приложения с заданным LLM и хранилищем."""

    def build(
        llm: object, store: ChunkVectorStore | object
    ) -> Iterator[TestClient]:
        runtime = Runtime(settings, embedder=fake_embedder, store=store, llm=llm)  # type: ignore[arg-type]
        return TestClient(create_app(settings, runtime))

    return build


def test_answered_response_has_citations(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    """Подтверждённая ссылка приходит с адресом фрагмента."""
    guideline = _manifest(settings)
    chunk = _chunk(guideline.guideline_id)
    memory_store.upsert([chunk], [[0.1] * 8])
    llm = FakeLLM(_thesis(), _answer())

    with client_factory(llm, memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": QUESTION}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"] == "Снижать до 140/90 [1]."
    assert body["citations"][0]["chunk_id"] == str(chunk.chunk_id)
    assert body["citations"][0]["page"] == 9
    assert body["citations"][0]["guideline_version"] == 1
    assert body["searched_guidelines"][0]["title"] == "Гипертензия"
    assert body["search"]["rewritten"] is True
    assert "text" not in body["citations"][0]
    # Текст чанка не должен утекать наружу ни в каком поле: цитата отдаётся как quote
    assert not _has_key(body, "text")


def _has_key(payload: object, key: str) -> bool:
    """Есть ли ключ в JSON-ответе на любом уровне вложенности."""
    if isinstance(payload, dict):
        return key in payload or any(_has_key(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_has_key(item, key) for item in payload)
    return False


def test_empty_question_is_bad_request(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    guideline = _manifest(settings)

    with client_factory(FakeLLM(), memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": "  "}
        )

    assert response.status_code == 400
    assert "question is required" in response.json()["detail"]


def test_no_guidelines_is_bad_request(client_factory, memory_store: ChunkVectorStore) -> None:
    with client_factory(FakeLLM(), memory_store) as client:
        response = client.post(ASK_PATH, json={"guideline_ids": [], "question": QUESTION})

    assert response.status_code == 400


def test_unknown_guideline_is_not_found(client_factory, memory_store: ChunkVectorStore) -> None:
    with client_factory(FakeLLM(), memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(uuid4())], "question": QUESTION}
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_not_ready_guideline_is_conflict(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    # `processing` на старте приложения снимается как прерванная индексация, поэтому
    # берём `uploaded`: он тоже не готов отвечать на вопросы
    guideline = _manifest(settings, status=GuidelineStatus.UPLOADED)

    with client_factory(FakeLLM(), memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": QUESTION}
        )

    assert response.status_code == 409
    assert "uploaded" in response.json()["detail"]


def test_llm_failure_is_bad_gateway(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    guideline = _manifest(settings)
    memory_store.upsert([_chunk(guideline.guideline_id)], [[0.1] * 8])
    llm = FakeLLM(LLMError("GigaChat request failed"))

    with client_factory(llm, memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": QUESTION}
        )

    assert response.status_code == 502
    assert "GigaChat" in response.json()["detail"]


def test_vector_store_failure_is_service_unavailable(
    client_factory, settings: Settings
) -> None:
    guideline = _manifest(settings)
    llm = FakeLLM(_thesis())

    with client_factory(llm, _RaisingStore()) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": QUESTION}
        )

    assert response.status_code == 503
    assert "vector store" in response.json()["detail"]


def test_not_found_status_keeps_search_context(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    """Отказ по существу вопроса сообщает, где искали."""
    guideline = _manifest(settings)
    memory_store.upsert([_chunk(guideline.guideline_id)], [[0.1] * 8])
    llm = FakeLLM(_thesis(), LlmAnswer(answer="Что-то", citations=[]))

    with client_factory(llm, memory_store) as client:
        response = client.post(
            ASK_PATH, json={"guideline_ids": [str(guideline.guideline_id)], "question": QUESTION}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_found"
    assert body["answer"] is None
    assert body["citations"] == []
    assert body["search"]["expression"]
    assert body["searched_guidelines"][0]["guideline_id"] == str(guideline.guideline_id)


def test_history_is_accepted_and_ignored_by_answer(
    client_factory, settings: Settings, memory_store: ChunkVectorStore
) -> None:
    """Лента принимается в запросе, но ответ строится по текущему вопросу."""
    guideline = _manifest(settings)
    chunk = _chunk(guideline.guideline_id)
    memory_store.upsert([chunk], [[0.1] * 8])
    llm = FakeLLM(_thesis(), _answer())

    with client_factory(llm, memory_store) as client:
        response = client.post(
            ASK_PATH,
            json={
                "guideline_ids": [str(guideline.guideline_id)],
                "question": QUESTION,
                "history": [
                    {"role": "user", "text": "предыдущий вопрос"},
                    {"role": "assistant", "text": "предыдущий ответ", "citations": []},
                ],
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "answered"
