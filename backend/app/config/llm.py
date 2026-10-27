"""Настройки LLM-провайдера и клиента GigaChat.

Локальные embeddings живут в отдельном домене — ``app/config/embedding.py``, параметры
чата — в ``app/config/chat.py``: слишком разные причины менять эти значения.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, field_validator

from app.config.base_settings import BACKEND_DIR, BaseEnvSettings


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


class LLMSettings(BaseEnvSettings):
    """Учётные данные GigaChat и параметры клиента.

    ``GIGACHAT_TOKEN`` — ключ авторизации из кабинета Studio: SDK обменивает его на
    access token и продлевает самостоятельно, поэтому в конфигурации только он. Ключи
    объявлены ``SecretStr``: не попадают в ``repr`` и логи.

    Проверка TLS по умолчанию выключена: сертификат НУЦ Минцифры ставится не всегда, а
    без него клиент падает на первом запросе. Для боевого режима включается
    ``GIGACHAT_VERIFY_SSL_CERTS=true`` вместе с путём к корневому сертификату.
    """

    llm_provider: LLMProvider = Field(
        default=LLMProvider.GIGACHAT,
        validation_alias="LLM_PROVIDER",
        description="Провайдер LLM: gigachat или deepseek",
    )
    gigachat_token: SecretStr | None = Field(
        default=None,
        validation_alias="GIGACHAT_TOKEN",
        description="Ключ авторизации GigaChat: SDK сам получает и продлевает токен",
    )
    gigachat_scope: str = Field(
        default="GIGACHAT_API_PERS",
        validation_alias="GIGACHAT_SCOPE",
        description="Scope API GigaChat: PERS для физлиц, B2B и CORP для юрлиц",
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
    gigachat_base_url: str = Field(
        default="https://api.giga.chat/v1",
        validation_alias="GIGACHAT_BASE_URL",
        description="Базовый адрес GigaChat API",
    )
    gigachat_structured_method: StructuredMethod = Field(
        default=StructuredMethod.FUNCTION_CALLING,
        validation_alias="GIGACHAT_STRUCTURED_METHOD",
        description="Как передаётся схема ответа: function_calling или json_schema",
    )
    gigachat_verify_ssl_certs: bool = Field(
        default=False,
        validation_alias="GIGACHAT_VERIFY_SSL_CERTS",
        description="Проверять TLS: включать вместе с корневым сертификатом Минцифры",
    )
    gigachat_ca_bundle_file: Path | None = Field(
        default=None,
        validation_alias="GIGACHAT_CA_BUNDLE_FILE",
        description="Путь к корневому сертификату НУЦ Минцифры",
    )
    gigachat_timeout: float = Field(
        default=60.0,
        gt=0,
        validation_alias="GIGACHAT_TIMEOUT",
        description="Таймаут запроса к GigaChat в секундах",
    )
    gigachat_max_retries: int = Field(
        default=3,
        ge=0,
        validation_alias="GIGACHAT_MAX_RETRIES",
        description="Повторы на 429 и 5xx внутри SDK",
    )
    deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="DEEPSEEK_API_KEY",
        description="API-ключ DeepSeek",
    )

    @field_validator("gigachat_ca_bundle_file")
    @classmethod
    def _anchor_ca_bundle(cls, value: Path | None) -> Path | None:
        """Относительный путь сертификата считать от ``backend/``."""
        if value is None or value.is_absolute():
            return value
        return BACKEND_DIR / value

    @property
    def gigachat_configured(self) -> bool:
        """Задан ли ключ: без него чат отвечает отказом, а не падает на старте."""
        return self.gigachat_token is not None
