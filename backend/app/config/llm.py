"""Настройки LLM-провайдера и клиента GigaChat.

Учётные данные GigaChat и параметры транспорта живут в ``app/config/gigachat.py``: тот же
ключ и тот же TLS нужны эмбеддингам. Здесь остаётся только то, что относится к чату —
выбор провайдера, имена моделей и способ передачи схемы ответа. Параметры чата — в
``app/config/chat.py``: слишком разные причины менять эти значения.
"""

from enum import StrEnum

from pydantic import Field, SecretStr

from app.config.gigachat import GigaChatSettings


class LLMProvider(StrEnum):
    """Провайдер LLM; выбирается переменной ``LLM_PROVIDER``."""

    GIGACHAT = "gigachat"
    DEEPSEEK = "deepseek"


class StructuredMethod(StrEnum):
    """Способ получить от модели ответ по схеме.

    ``function_calling`` — схема передаётся описанием функции: работает на всех моделях.
    ``json_schema`` — нативное ограничение ``response_format``: точнее, но пока beta.
    """

    FUNCTION_CALLING = "function_calling"
    JSON_SCHEMA = "json_schema"


class LLMSettings(GigaChatSettings):
    """Провайдер LLM, модели и учётные данные GigaChat.

    Наследование от ``GigaChatSettings`` даёт плоские поля ``gigachat_*``: ключ
    авторизации читается из той же переменной, что и клиентом эмбеддингов, поэтому
    расхождение между чатом и эмбеддингами невозможно.
    """

    llm_provider: LLMProvider = Field(
        default=LLMProvider.GIGACHAT,
        validation_alias="LLM_PROVIDER",
        description="Провайдер LLM: gigachat или deepseek",
    )
    gigachat_model: str = Field(
        default="GigaChat-3-Ultra",
        validation_alias="GIGACHAT_MODEL",
        description="Модель, которая отвечает на вопрос",
    )
    gigachat_rewrite_model: str = Field(
        default="GigaChat-2",
        validation_alias="GIGACHAT_REWRITE_MODEL",
        description="Модель переписывания запроса: задача проще, ответ дешевле",
    )
    gigachat_structured_method: StructuredMethod = Field(
        default=StructuredMethod.FUNCTION_CALLING,
        validation_alias="GIGACHAT_STRUCTURED_METHOD",
        description="Как передаётся схема ответа: function_calling или json_schema",
    )
    deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
        description="API-ключ DeepSeek",
    )
