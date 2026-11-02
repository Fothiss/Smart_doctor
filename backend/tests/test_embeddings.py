"""Проверки клиента эмбеддингов GigaChat: порядок векторов, сверки и отказы."""

from typing import Any

import pytest
from gigachat.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ResponseError,
)
from pydantic import BaseModel, ValidationError

from app.clients.embeddings import (
    EmbeddingAuthError,
    EmbeddingError,
    EmbeddingResult,
    GigaChatEmbedder,
    build_embedder,
)
from app.config import EmbeddingSettings

DIMENSION = 4
"""Размерность подменённых векторов: настоящие 2560 в тестах не нужны."""

MODEL = "EmbeddingsGigaR"


class FakeUsage:
    """Заглушка статистики запроса."""

    def __init__(self, prompt_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens


class FakeItem:
    """Один элемент ответа сервиса эмбеддингов."""

    def __init__(self, index: int, embedding: list[float], prompt_tokens: int = 5) -> None:
        self.index = index
        self.embedding = embedding
        self.usage = FakeUsage(prompt_tokens)


class FakeResponse:
    """Ответ сервиса эмбеддингов в форме, которую отдаёт SDK."""

    def __init__(self, items: list[FakeItem], model: str | None = MODEL) -> None:
        self.data = items
        self.model = model


class FakeClient:
    """Подмена клиента GigaChat: помнит запросы и отдаёт заданный ответ."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[tuple[list[str], str]] = []

    def embeddings(self, texts: list[str], model: str) -> Any:
        """Запомнить аргументы и вернуть заготовленный ответ."""
        self.calls.append((list(texts), model))
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def _settings(**overrides: Any) -> EmbeddingSettings:
    """Настройки без обращения к окружению."""
    values: dict[str, Any] = {
        "dimension": DIMENSION,
        "model_id": MODEL,
        "query_template": "Найди абзац. Вопрос: {text}",
        "gigachat_token": "test-key",
    }
    values.update(overrides)
    return EmbeddingSettings(**values)


def _vector(value: float) -> list[float]:
    """Вектор нужной тестовой размерности."""
    return [value] * DIMENSION


def _embedder(response: Any, **overrides: Any) -> tuple[GigaChatEmbedder, FakeClient]:
    """Эмбеддер с подменённым клиентом."""
    embedder = GigaChatEmbedder(_settings(**overrides))
    client = FakeClient(response)
    embedder._client = client  # type: ignore[assignment]
    return embedder, client


def test_documents_are_returned_in_request_order() -> None:
    """Векторы раскладываются по `index`, а не по порядку элементов в ответе."""
    response = FakeResponse(
        [FakeItem(index=1, embedding=_vector(2.0)), FakeItem(index=0, embedding=_vector(1.0))]
    )
    embedder, client = _embedder(response)

    result = embedder.encode_documents(["первый", "второй"])

    assert result.vectors == [_vector(1.0), _vector(2.0)]
    assert client.calls == [(["первый", "второй"], MODEL)]


def test_tokens_are_summed_over_response_items() -> None:
    """Стоимость запроса складывается из `usage.prompt_tokens` каждого элемента."""
    response = FakeResponse(
        [
            FakeItem(index=0, embedding=_vector(1.0), prompt_tokens=11),
            FakeItem(index=1, embedding=_vector(2.0), prompt_tokens=7),
        ]
    )
    embedder, _ = _embedder(response)

    result = embedder.encode_documents(["а", "б"])

    assert result == EmbeddingResult(vectors=[_vector(1.0), _vector(2.0)], tokens=18)


def test_query_gets_exactly_one_prefix() -> None:
    """Запрос получает ровно один шаблон, документы — ни одного.

    Двойной префикс не падает и не логируется: он просто тихо ухудшает поиск, поэтому
    проверяется отдельно.
    """
    single = FakeResponse([FakeItem(index=0, embedding=_vector(1.0))])
    embedder, client = _embedder(single)

    embedder.encode_documents(["фрагмент клинрека"])
    embedder.encode_query("жалобы пациента")

    assert client.calls[0][0] == ["фрагмент клинрека"]
    assert client.calls[1][0] == ["Найди абзац. Вопрос: жалобы пациента"]
    assert client.calls[1][0][0].count("Вопрос:") == 1


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["нормально", ""]])
def test_empty_text_is_rejected_before_the_request(texts: list[str]) -> None:
    """Пустой фрагмент — отказ до обращения к сервису, а не вектор из служебных токенов."""
    embedder, client = _embedder(FakeResponse([FakeItem(index=0, embedding=_vector(1.0))]))

    with pytest.raises(EmbeddingError):
        embedder.encode_documents(texts)

    assert client.calls == []


def test_empty_text_position_is_reported_without_the_text() -> None:
    """Причина называет позицию в порции и не содержит текста фрагмента."""
    embedder, _ = _embedder(FakeResponse([]))

    with pytest.raises(EmbeddingError) as error:
        embedder.encode_documents(["секретный текст пациента", "  "])

    assert "position 1" in str(error.value)
    assert "секретный текст" not in str(error.value)


def test_missing_index_is_rejected() -> None:
    """Ответ без части элементов не превращается в дырявый список векторов."""
    embedder, _ = _embedder(FakeResponse([FakeItem(index=0, embedding=_vector(1.0))]))

    with pytest.raises(EmbeddingError, match="misses"):
        embedder.encode_documents(["первый", "второй"])


def test_repeated_index_is_rejected() -> None:
    """Повтор индекса означает, что векторы нельзя сопоставить с фрагментами."""
    embedder, _ = _embedder(
        FakeResponse(
            [FakeItem(index=0, embedding=_vector(1.0)), FakeItem(index=0, embedding=_vector(2.0))]
        )
    )

    with pytest.raises(EmbeddingError, match="repeats"):
        embedder.encode_documents(["первый", "второй"])


def test_unexpected_model_is_rejected() -> None:
    """Векторы чужой модели не попадают в метаданные клинрека как свои."""
    embedder, _ = _embedder(
        FakeResponse([FakeItem(index=0, embedding=_vector(1.0))], model="Embeddings")
    )

    with pytest.raises(EmbeddingError, match="Embeddings"):
        embedder.encode_documents(["фрагмент"])


def test_unexpected_dimension_is_rejected() -> None:
    """Вектор другой размерности не доходит до хранилища."""
    embedder, _ = _embedder(
        FakeResponse([FakeItem(index=0, embedding=[0.1, 0.2])])
    )

    with pytest.raises(EmbeddingError, match="2-dimensional"):
        embedder.encode_documents(["фрагмент"])


def test_rejected_key_is_reported_as_auth_error() -> None:
    """Отклонённый ключ или закрытая модель — отдельный класс ошибки."""
    error = AuthenticationError("https://api.giga.chat/v1/embeddings", 401, b"", None)
    embedder, _ = _embedder(error)

    with pytest.raises(EmbeddingAuthError, match="401"):
        embedder.encode_documents(["фрагмент"])


def test_rate_limit_is_reported_as_unavailable() -> None:
    """Исчерпанные повторы по 429 выглядят как недоступность сервиса."""
    error = RateLimitError("https://api.giga.chat/v1/embeddings", 429, b"", None)
    embedder, _ = _embedder(error)

    with pytest.raises(EmbeddingError, match="unavailable"):
        embedder.encode_documents(["фрагмент"])


def test_bad_key_on_oauth_endpoint_is_auth_error() -> None:
    """Неверный ключ приходит как `400` от OAuth-сервера — это отказ в доступе."""
    error = BadRequestError(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth", 400, b"", None
    )
    embedder, _ = _embedder(error)

    with pytest.raises(EmbeddingAuthError, match="authorization key"):
        embedder.encode_documents(["фрагмент"])


def test_bad_request_to_api_endpoint_is_not_auth_error() -> None:
    """Ошибка в теле запроса остаётся ошибкой запроса, а не отказом в доступе."""
    error = BadRequestError("https://api.giga.chat/v1/embeddings", 400, b"", None)
    embedder, _ = _embedder(error)

    with pytest.raises(EmbeddingError) as caught:
        embedder.encode_documents(["фрагмент"])

    assert not isinstance(caught.value, EmbeddingAuthError)


def test_unexpected_response_shape_is_reported_as_embedding_error() -> None:
    """Несовпадение формата ответа не выходит наружу как pydantic-ошибка."""

    class Payload(BaseModel):
        value: int

    try:
        Payload(value="не число")
    except ValidationError as exc:
        validation_error = exc

    embedder, _ = _embedder(validation_error)

    with pytest.raises(EmbeddingError, match="unexpected"):
        embedder.encode_documents(["фрагмент"])


def test_missing_token_fails_on_first_use() -> None:
    """Без ключа отказ выдаётся при первом обращении, а не при сборке приложения."""
    embedder = GigaChatEmbedder(_settings(gigachat_token=None))

    with pytest.raises(EmbeddingAuthError, match="GIGACHAT_TOKEN"):
        embedder.encode_documents(["фрагмент"])


def test_build_embedder_uses_settings() -> None:
    """Фабрика отдаёт эмбеддер с моделью и размерностью из настроек."""
    embedder = build_embedder(_settings())

    assert embedder.model_id == MODEL
    assert embedder.dimension == DIMENSION
    assert isinstance(embedder, GigaChatEmbedder)


def test_error_does_not_leak_response_body() -> None:
    """Причина отказа хранит только код, а не тело ответа сервиса."""
    error = ResponseError(
        "https://api.giga.chat/v1/embeddings", 500, b"internal payload", None
    )
    embedder, _ = _embedder(error)

    with pytest.raises(EmbeddingError) as caught:
        embedder.encode_documents(["фрагмент"])

    assert "internal payload" not in str(caught.value)
