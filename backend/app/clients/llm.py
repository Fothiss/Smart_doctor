"""Клиент LLM на GigaChat.

Единственное место, где проект разговаривает с моделью: сервисы получают интерфейс
``LLMClient`` и не знают ни провайдера, ни транспорта. Смена провайдера — работа только
в этом модуле.

Клиент на ``langchain-gigachat``: ``credentials`` — ключ авторизации из окружения, SDK
сам обменивает его на access token и продлевает. Структурированный вывод идёт через
``with_structured_output``: схема Pydantic превращается в описание функции (или в
нативный ``response_format``), а ответ приходит уже провалидированным объектом.
"""

import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from gigachat.exceptions import AuthenticationError, GigaChatException, UnprocessableEntityError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_gigachat import GigaChat
from pydantic import BaseModel

from app.config.llm import LLMSettings

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

ChainFactory = Callable[[str, type[BaseModel]], Any]
"""Собирает цепочку structured output для модели и схемы; подменяется в тестах."""


class LLMError(Exception):
    """Модель недоступна, отказала или вернула ответ не по схеме."""


class LLMAuthError(LLMError):
    """Ключ авторизации отклонён провайдером."""


class ModelRole(StrEnum):
    """Зачем зовём модель: ответ и переписывание запроса стоят по-разному."""

    ANSWER = "answer"
    REWRITE = "rewrite"


class LLMClient(Protocol):
    """Интерфейс модели: сервисам нужны роль и схема ответа, а не провайдер."""

    def model_for(self, role: ModelRole) -> str:
        """Имя модели, которой будет выполнен вызов роли."""
        ...

    async def structured(
        self,
        system: str,
        human: str,
        schema: type[ModelT],
        *,
        role: ModelRole = ModelRole.ANSWER,
    ) -> ModelT:
        """Получить ответ, соответствующий схеме."""
        ...


class GigaChatClient:
    """GigaChat через ``langchain-gigachat``.

    Клиенты моделей создаются лениво и переиспользуются: у SDK свой пул соединений,
    а модель ответа и модель переписывания — разные экземпляры.
    """

    def __init__(
        self, settings: LLMSettings, chain_factory: ChainFactory | None = None
    ) -> None:
        self._settings = settings
        self._models: dict[str, GigaChat] = {}
        self._chain_factory = chain_factory

    def model_for(self, role: ModelRole) -> str:
        """Имя модели для роли: ответ — тяжёлая, переписывание — лёгкая."""
        if role is ModelRole.REWRITE:
            return self._settings.gigachat_rewrite_model
        return self._settings.gigachat_model

    def _model(self, name: str) -> GigaChat:
        """Клиент конкретной модели; создаётся при первом обращении."""
        client = self._models.get(name)
        if client is None:
            settings = self._settings
            if settings.gigachat_token is None:
                raise LLMAuthError("GIGACHAT_TOKEN is not set")
            client = GigaChat(
                credentials=settings.gigachat_token.get_secret_value(),
                scope=settings.gigachat_scope,
                model=name,
                base_url=settings.gigachat_base_url,
                verify_ssl_certs=settings.gigachat_verify_ssl_certs,
                ca_bundle_file=(
                    str(settings.gigachat_ca_bundle_file)
                    if settings.gigachat_ca_bundle_file is not None
                    else None
                ),
                timeout=settings.gigachat_timeout,
                max_retries=settings.gigachat_max_retries,
                temperature=0.0,
            )
            self._models[name] = client
        return client

    def _build_chain(self, name: str, schema: type[BaseModel]) -> Any:
        """Собрать цепочку structured output для модели."""
        return self._model(name).with_structured_output(
            schema,
            include_raw=True,
            method=self._settings.gigachat_structured_method.value,
        )

    async def structured(
        self,
        system: str,
        human: str,
        schema: type[ModelT],
        *,
        role: ModelRole = ModelRole.ANSWER,
    ) -> ModelT:
        """Вызвать модель и вернуть разобранный ответ.

        Провал разбора и ответ, не соответствующий схеме, — это ``LLMError``, а не
        пустой объект: без валидного ответа сервис не должен продолжать работу.
        """
        chain = (self._chain_factory or self._build_chain)(self.model_for(role), schema)
        messages = [SystemMessage(content=system), HumanMessage(content=human)]
        try:
            result = await chain.ainvoke(messages)
        except AuthenticationError as exc:
            raise LLMAuthError("GigaChat rejected the authorization key") from exc
        except UnprocessableEntityError as exc:
            raise LLMError(f"GigaChat rejected the request: {exc}") from exc
        except GigaChatException as exc:
            raise LLMError(f"GigaChat request failed: {exc}") from exc
        except TimeoutError as exc:
            raise LLMError("GigaChat request timed out") from exc

        return _parsed(result, schema)


def _parsed[T: BaseModel](result: Any, schema: type[T]) -> T:
    """Достать разобранный ответ из результата ``include_raw=True``.

    ``with_structured_output`` с ``include_raw`` возвращает словарь с ``parsed``,
    ``parsing_error`` и ``raw``. Ошибку разбора нельзя проглатывать: ответ без
    валидной схемы не годится.
    """
    if isinstance(result, schema):
        return result
    if not isinstance(result, dict):
        raise LLMError(f"unexpected structured output: {type(result).__name__}")
    error = result.get("parsing_error")
    if error is not None:
        raise LLMError(f"model answer does not match the schema: {error}")
    parsed = result.get("parsed")
    if parsed is None:
        raise LLMError("model returned no structured answer")
    return parsed


def build_llm_client(
    settings: LLMSettings, chain_factory: ChainFactory | None = None
) -> GigaChatClient:
    """Собрать клиент провайдера из настроек.

    Единственная точка, где выбирается провайдер: остальной код работает с ``LLMClient``.
    """
    return GigaChatClient(settings, chain_factory)
