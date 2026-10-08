"""Настройки хранилищ данных: PostgreSQL и Qdrant."""

from pydantic import Field

from app.config.base_settings import BaseEnvSettings


class DatabaseNotConfiguredError(RuntimeError):
    """Обращение к PostgreSQL без заданного ``DATABASE_URL``."""


class DatabaseSettings(BaseEnvSettings):
    """Подключения к PostgreSQL и Qdrant.

    ``DATABASE_URL`` без рабочего значения по умолчанию: DSN с паролем не хранится
    в коде. Пока эндпоинты БД не используют (см. README), переменная может быть
    не задана; обращение к ней через :attr:`sqlalchemy_url` падает явно, а не
    подключается к случайной локальной базе.
    """

    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
        description="DSN PostgreSQL, например postgresql+psycopg://user:pass@host:5432/db",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        validation_alias="QDRANT_URL",
        description="Адрес Qdrant для векторного поиска",
    )

    @property
    def sqlalchemy_url(self) -> str:
        """DSN для SQLAlchemy; явная ошибка, если подключение не сконфигурировано."""
        if self.database_url is None:
            raise DatabaseNotConfiguredError("DATABASE_URL is not set")
        return self.database_url
