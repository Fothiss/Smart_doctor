"""Проверки клиента LLM: подмена цепочки, ошибки провайдера, разбор ответа."""

from typing import Any

import pytest
from gigachat.exceptions import AuthenticationError, GigaChatException, UnprocessableEntityError
from pydantic import BaseModel

from app.clients.llm import (
    GigaChatClient,
    LLMAuthError,
    LLMError,
    ModelRole,
    build_llm_client,
)
from app.config import LLMSettings, StructuredMethod

URL = "https://api.giga.chat/v1/chat/completions"


class Answer(BaseModel):
    """Минимальная схема ответа для проверок."""

    text: str


class _FakeChain:
    """Цепочка structured output: возвращает заданный результат или бросает исключение."""

    def __init__(self, result: Any) -> None:
        self._result = result
        self.messages: Any = None

    async def ainvoke(self, messages: Any) -> Any:
        if isinstance(self._result, BaseException):
            raise self._result
        self.messages = messages
        return self._result


def _client(result: Any, **settings: Any) -> tuple[GigaChatClient, list[tuple[str, type]]]:
    """Клиент с подменённой цепочкой и журналом сборки цепочек."""
    calls: list[tuple[str, type]] = []
    settings.setdefault("gigachat_token", "authorization-key")

    def factory(model: str, schema: type) -> _FakeChain:
        calls.append((model, schema))
        return _FakeChain(result)

    return GigaChatClient(LLMSettings(**settings), chain_factory=factory), calls


async def test_valid_answer_is_returned_parsed() -> None:
    """Разобранный ответ отдаётся как объект схемы, а не как словарь."""
    client, calls = _client({"parsed": Answer(text="ответ"), "parsing_error": None, "raw": None})

    answer = await client.structured("система", "вопрос", Answer)

    assert answer == Answer(text="ответ")
    assert calls[0][1] is Answer


async def test_parsing_error_becomes_llm_error() -> None:
    """Ответ мимо схемы — отказ, а не пустой объект."""
    client, _ = _client({"parsed": None, "parsing_error": ValueError("bad json"), "raw": None})

    with pytest.raises(LLMError, match="does not match the schema"):
        await client.structured("система", "вопрос", Answer)


async def test_missing_parsed_answer_is_rejected() -> None:
    """Пустой разбор — тоже отказ: продолжать без ответа нельзя."""
    client, _ = _client({"parsed": None, "parsing_error": None, "raw": None})

    with pytest.raises(LLMError, match="no structured answer"):
        await client.structured("система", "вопрос", Answer)


async def test_unexpected_payload_is_rejected() -> None:
    """Неожидаемая форма результата не должна молча превращаться в ответ."""
    client, _ = _client("строка вместо словаря")

    with pytest.raises(LLMError, match="unexpected structured output"):
        await client.structured("система", "вопрос", Answer)


async def test_authentication_error_is_mapped() -> None:
    """Отказ авторизации назван отдельным типом: причина — ключ, а не запрос."""
    error = AuthenticationError(URL, 401, b"{}", None)
    client, _ = _client(error)

    with pytest.raises(LLMAuthError):
        await client.structured("система", "вопрос", Answer)


async def test_unprocessable_entity_is_mapped() -> None:
    """Отказ валидации запроса (в том числе слишком длинный контекст) — LLMError."""
    client, _ = _client(UnprocessableEntityError(URL, 422, b"{}", None))

    with pytest.raises(LLMError, match="rejected the request"):
        await client.structured("система", "вопрос", Answer)


async def test_gigachat_exception_is_mapped() -> None:
    """Прочие отказы провайдера не проходят наружу как есть."""
    client, _ = _client(GigaChatException("boom"))

    with pytest.raises(LLMError, match="request failed"):
        await client.structured("система", "вопрос", Answer)


async def test_timeout_is_mapped() -> None:
    """Таймаут — понятная ошибка, а не голое исключение стандартной библиотеки."""
    client, _ = _client(TimeoutError())

    with pytest.raises(LLMError, match="timed out"):
        await client.structured("система", "вопрос", Answer)


async def test_missing_token_is_reported_before_network() -> None:
    """Без ключа клиент не идёт в сеть и не создаёт модель."""
    client = GigaChatClient(LLMSettings(gigachat_token=None))

    with pytest.raises(LLMAuthError, match="GIGACHAT_TOKEN"):
        await client.structured("система", "вопрос", Answer)


def test_roles_use_different_models() -> None:
    """Ответ и переписывание идут в разные модели: у них разная цена."""
    client = build_llm_client(
        LLMSettings(
            gigachat_token="key",
            gigachat_model="GigaChat-3-Ultra",
            gigachat_rewrite_model="GigaChat-2",
        )
    )

    assert client.model_for(ModelRole.ANSWER) == "GigaChat-3-Ultra"
    assert client.model_for(ModelRole.REWRITE) == "GigaChat-2"


async def test_rewrite_role_passes_rewrite_model() -> None:
    """Роль переписывания доходит до фабрики цепочек."""
    client, calls = _client(
        {"parsed": Answer(text="ok"), "parsing_error": None, "raw": None},
        gigachat_model="GigaChat-3-Ultra",
        gigachat_rewrite_model="GigaChat-2",
    )

    await client.structured("система", "вопрос", Answer, role=ModelRole.REWRITE)

    assert calls[0][0] == "GigaChat-2"


def test_structured_method_defaults_to_function_calling() -> None:
    """Схема по умолчанию передаётся описанием функции: работает на всех моделях."""
    settings = LLMSettings(_env_file=None)

    assert settings.gigachat_structured_method is StructuredMethod.FUNCTION_CALLING
