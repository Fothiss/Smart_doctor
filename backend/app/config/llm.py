"""Настройки LLM-провайдера и локальных embeddings."""

from enum import StrEnum

from pydantic import Field, SecretStr

from app.config.base_settings import BaseEnvSettings


class LLMProvider(StrEnum):
    """Провайдер LLM; выбирается переменной ``LLM_PROVIDER``."""

    GIGACHAT = "gigachat"
    DEEPSEEK = "deepseek"


class LLMSettings(BaseEnvSettings):
    """Выбор провайдера и его учётные данные.

    Ключи объявлены как ``SecretStr``: не попадают в ``repr`` и логи. Пустые значения
    допустимы, пока клиент LLM не реализован; неизвестный ``LLM_PROVIDER`` роняет
    старт, а не откатывается молча к GigaChat.
    """

    llm_provider: LLMProvider = Field(
        default=LLMProvider.GIGACHAT,
        validation_alias="LLM_PROVIDER",
        description="Провайдер LLM: gigachat или deepseek",
    )
    gigachat_auth_key: SecretStr | None = Field(
        default=None,
        validation_alias="GIGACHAT_AUTH_KEY",
        description="Ключ авторизации GigaChat",
    )
    gigachat_scope: str = Field(
        default="GIGACHAT_API_PERS",
        validation_alias="GIGACHAT_SCOPE",
        description="Scope GigaChat",
    )
    deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
        description="API-ключ DeepSeek",
    )
    embedding_model: str = Field(
        default="sergeyzh/BERTA",
        validation_alias="EMBEDDING_MODEL",
        description="Модель локальных embeddings",
    )
