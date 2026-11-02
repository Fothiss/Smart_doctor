"""Клиент эмбеддингов GigaChat.

Единственное место, где проект считает векторы: сервисы получают интерфейс ``Embedder``
и не знают ни провайдера, ни транспорта. Смена провайдера — работа только в этом модуле.

Клиент на ``gigachat``: ключ авторизации обменивается на access token, который SDK сам
продлевает (за 60 с до истечения), а повторы на 429 и 5xx с учётом ``Retry-After``
выполняются внутри SDK. Клиент создаётся один раз за время жизни процесса и не
закрывается: ``with`` из примеров документации нужен только ради ``close()`` в конце
блока, а соединения и токен переиспользуются.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from gigachat import GigaChat
from gigachat.exceptions import (
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    GigaChatException,
    RateLimitError,
    ResponseError,
    ServerError,
    UnprocessableEntityError,
)
from pydantic import ValidationError

from app.config.embedding import EmbeddingSettings

logger = logging.getLogger(__name__)

AUTH_ENDPOINT_MARKER = "/oauth"
"""Фрагмент адреса OAuth-сервера: по нему распознаётся отказ в авторизации."""


class EmbeddingError(Exception):
    """Сервис эмбеддингов недоступен, отказал или вернул непригодный ответ."""


class EmbeddingAuthError(EmbeddingError):
    """Ключ авторизации отклонён или у него нет доступа к модели."""


@dataclass(frozen=True)
class EmbeddingResult:
    """Векторы и стоимость запроса.

    Токены возвращаются вместе с векторами, а не хранятся в состоянии клиента: клиент
    один на процесс, и параллельный поиск запроса из чата подмешал бы свои токены в
    сумму по клинреку.
    """

    vectors: list[list[float]]
    tokens: int


class Embedder(Protocol):
    """Интерфейс эмбеддера: индексации и поиску нужен только он."""

    @property
    def dimension(self) -> int:
        """Размерность вектора."""
        ...

    @property
    def model_id(self) -> str:
        """Идентификатор модели: попадает в метаданные клинрека."""
        ...

    def encode_documents(self, texts: Sequence[str]) -> EmbeddingResult:
        """Посчитать векторы фрагментов клинрека."""
        ...

    def encode_query(self, text: str) -> list[float]:
        """Посчитать вектор поискового запроса."""
        ...


def _looks_like_auth_failure(error: ResponseError) -> bool:
    """Отказ вызван отклонённым ключом авторизации, а не ошибкой в запросе.

    GigaChat отвечает на неверный ключ `400` от адреса авторизации, а не `401`: код и тело
    ответа совпадают с ошибкой в теле запроса, поэтому класс ошибки определяется по адресу,
    с которого пришёл отказ.
    """
    return AUTH_ENDPOINT_MARKER in str(error.url)


def _check_texts(texts: Sequence[str]) -> list[str]:
    """Проверить вход и вернуть его списком.

    Пустой текст сервис принимает и возвращает вектор из служебных токенов: ошибки не
    будет, а поиск по такому фрагменту бессмыслен. Поэтому пустой фрагмент — отказ, а не
    пропуск: пропущенный чанк молча выпал бы из поиска. Позиция в порции попадает в
    причину, текст — нет.
    """
    prepared = list(texts)
    if not prepared:
        raise EmbeddingError("no texts to encode")
    for position, text in enumerate(prepared):
        if not text.strip():
            raise EmbeddingError(f"text at position {position} is empty")
    return prepared


def _sort_by_index(items: Sequence[object], expected: int) -> list[list[float]]:
    """Разложить векторы по индексам ответа и вернуть их в порядке входа.

    ``index`` — индекс строки в исходном массиве. Порядок списка в JSON полагать нельзя:
    перепутанный вектор молча привязал бы чужой текст к фрагменту, а вердикт ссылается
    на конкретный чанк.
    """
    ordered: dict[int, list[float]] = {}
    for item in items:
        index = getattr(item, "index", None)
        vector = getattr(item, "embedding", None)
        if not isinstance(index, int) or not isinstance(vector, list):
            raise EmbeddingError("embedding response has an unreadable item")
        if index in ordered:
            raise EmbeddingError(f"embedding response repeats index {index}")
        ordered[index] = vector
    missing = sorted(set(range(expected)) - ordered.keys())
    if missing:
        raise EmbeddingError(f"embedding response misses items: {missing}")
    extra = sorted(ordered.keys() - set(range(expected)))
    if extra:
        raise EmbeddingError(f"embedding response has unexpected items: {extra}")
    return [ordered[index] for index in range(expected)]


class GigaChatEmbedder:
    """Эмбеддинги через GigaChat API.

    Модель передаётся в каждом запросе, поэтому один клиент годится для любой модели:
    транспорт настроен один раз, а имя модели приходит из настроек и попадает в
    метаданные клинрека.
    """

    def __init__(self, settings: EmbeddingSettings) -> None:
        self._settings = settings
        self._client: GigaChat | None = None

    @property
    def dimension(self) -> int:
        """Размерность вектора из настроек."""
        return self._settings.dimension

    @property
    def model_id(self) -> str:
        """Идентификатор модели из настроек."""
        return self._settings.model_id

    def _load(self) -> GigaChat:
        """Создать клиент один раз за время жизни процесса.

        Без ключа отказ выдаётся здесь, а не на старте: загрузка, просмотр и валидация
        формы обязаны работать без настроенного GigaChat.
        """
        if self._client is not None:
            return self._client
        settings = self._settings
        if settings.gigachat_token is None:
            raise EmbeddingAuthError("GIGACHAT_TOKEN is not set")
        self._client = GigaChat(
            credentials=settings.gigachat_token.get_secret_value(),
            scope=settings.gigachat_scope,
            base_url=settings.gigachat_base_url,
            verify_ssl_certs=settings.gigachat_verify_ssl_certs,
            ca_bundle_file=settings.ca_bundle_path,
            timeout=settings.gigachat_timeout,
            max_retries=settings.gigachat_max_retries,
        )
        logger.info("Embedding model: %s", settings.model_id)
        return self._client

    def _request(self, texts: list[str]) -> object:
        """Один запрос к сервису эмбеддингов с переводом отказов."""
        client = self._load()
        try:
            return client.embeddings(texts, model=self._settings.model_id)
        except (AuthenticationError, ForbiddenError) as exc:
            raise EmbeddingAuthError(
                f"GigaChat rejected the authorization key or model access: {exc.status_code}"
            ) from exc
        except (RateLimitError, ServerError) as exc:
            raise EmbeddingError(
                f"embedding service is unavailable after retries: {exc.status_code}"
            ) from exc
        except (BadRequestError, UnprocessableEntityError) as exc:
            if _looks_like_auth_failure(exc):
                raise EmbeddingAuthError(
                    f"GigaChat rejected the authorization key for embeddings: {exc.status_code}"
                ) from exc
            raise EmbeddingError(
                f"embedding service rejected the request: {exc.status_code}"
            ) from exc
        except GigaChatException as exc:
            # Только тип: текст исключения SDK может содержать тело ответа сервиса
            raise EmbeddingError(f"embedding request failed: {type(exc).__name__}") from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise EmbeddingError(f"embedding service is unreachable: {type(exc).__name__}") from exc
        except ValidationError as exc:
            raise EmbeddingError(
                f"unexpected embedding response: {exc.error_count()} errors"
            ) from exc

    def encode_documents(self, texts: Sequence[str]) -> EmbeddingResult:
        """Кодировать документы: инструкция к ним не добавляется."""
        prepared = _check_texts(texts)
        response = self._request(prepared)
        model = getattr(response, "model", None)
        if model is not None and model != self._settings.model_id:
            raise EmbeddingError(
                f"embedding service answered with model {model}, "
                f"but {self._settings.model_id} was requested"
            )
        items = getattr(response, "data", None)
        if not isinstance(items, list):
            raise EmbeddingError("embedding response has no data")
        vectors = _sort_by_index(items, len(prepared))
        for vector in vectors:
            if len(vector) != self._settings.dimension:
                raise EmbeddingError(
                    f"embedding service returned a {len(vector)}-dimensional vector, "
                    f"but {self._settings.dimension} is configured"
                )
        tokens = 0
        for item in items:
            usage = getattr(item, "usage", None)
            tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        return EmbeddingResult(vectors=vectors, tokens=tokens)

    def encode_query(self, text: str) -> list[float]:
        """Кодировать запрос: инструкция добавляется ровно один раз."""
        query = self._settings.build_query(text)
        return self.encode_documents([query]).vectors[0]


def build_embedder(settings: EmbeddingSettings) -> Embedder:
    """Собрать эмбеддер из настроек.

    Единственная точка, где выбирается провайдер эмбеддингов: остальной код работает с
    ``Embedder``. Сейчас провайдер один — GigaChat.
    """
    return GigaChatEmbedder(settings)
