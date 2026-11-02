"""Общие настройки доступа к GigaChat API.

Ключ авторизации, scope, адрес, TLS и повторы нужны двум независимым доменам: чату
(``app/config/llm.py``) и эмбеддингам (``app/config/embedding.py``). Объявлены один раз
здесь, а домены наследуются — иначе одну и ту же переменную окружения объявляли бы
дважды, и значения могли разъехаться (например, проверка TLS в чате включена, а в
эмбеддингах забыта).

Поля остаются плоскими и с префиксом ``gigachat_``: публичные свойства настроек чата
(``settings.llm.gigachat_token``) не меняются.
"""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator

from app.config.base_settings import BACKEND_DIR, BaseEnvSettings


class GigaChatSettings(BaseEnvSettings):
    """Учётные данные GigaChat и параметры транспорта.

    ``GIGACHAT_TOKEN`` — ключ авторизации из кабинета Studio: SDK обменивает его на
    access token и продлевает самостоятельно, поэтому в конфигурации только он. Ключ
    объявлен ``SecretStr``: не попадает в ``repr`` и логи.

    Проверка TLS по умолчанию выключена: сертификат НУЦ Минцифры ставится не всегда, а
    без него клиент падает на первом запросе. Для боевого режима включается
    ``GIGACHAT_VERIFY_SSL_CERTS=true`` вместе с путём к корневому сертификату.
    """

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
    gigachat_base_url: str = Field(
        default="https://api.giga.chat/v1",
        validation_alias="GIGACHAT_BASE_URL",
        description="Базовый адрес GigaChat API",
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

    @field_validator("gigachat_ca_bundle_file")
    @classmethod
    def _anchor_ca_bundle(cls, value: Path | None) -> Path | None:
        """Относительный путь сертификата считать от ``backend/``."""
        if value is None or value.is_absolute():
            return value
        return BACKEND_DIR / value

    @property
    def gigachat_configured(self) -> bool:
        """Задан ли ключ: без него запрос отвечает отказом, а не падает на старте."""
        return self.gigachat_token is not None

    @property
    def ca_bundle_path(self) -> str | None:
        """Путь к сертификату строкой — в таком виде его ждёт клиент GigaChat."""
        return (
            str(self.gigachat_ca_bundle_file)
            if self.gigachat_ca_bundle_file is not None
            else None
        )
