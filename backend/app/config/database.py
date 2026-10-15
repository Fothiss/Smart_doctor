"""Настройки хранилищ данных: PostgreSQL и Qdrant."""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from app.config.base_settings import BACKEND_DIR, BaseEnvSettings


class DatabaseNotConfiguredError(RuntimeError):
    """Обращение к PostgreSQL без заданного ``DATABASE_URL``."""


class QdrantMode(StrEnum):
    """Режим векторного хранилища; выбирается переменной ``QDRANT_MODE``."""

    LOCAL = "local"
    SERVER = "server"


class DatabaseSettings(BaseEnvSettings):
    """Подключения к PostgreSQL и Qdrant.

    ``DATABASE_URL`` без рабочего значения по умолчанию: DSN с паролем не хранится
    в коде. Пока эндпоинты БД не используют (см. README), переменная может быть
    не задана; обращение к ней через :attr:`sqlalchemy_url` падает явно, а не
    подключается к случайной локальной базе.

    Режим Qdrant задан явно: неявный выбор «есть URL — значит сервер» уводил бы
    локальный запуск в сеть по адресу из Docker Compose и ронял его на
    несуществующем хосте.
    """

    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
        description="DSN PostgreSQL, например postgresql+psycopg://user:pass@host:5432/db",
    )
    qdrant_mode: QdrantMode = Field(
        default=QdrantMode.LOCAL,
        validation_alias="QDRANT_MODE",
        description="local — хранилище в каталоге, server — сервер Qdrant по QDRANT_URL",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        validation_alias="QDRANT_URL",
        description="Адрес Qdrant для векторного поиска (режим server)",
    )
    qdrant_local_path: Path = Field(
        default=Path("storage/qdrant"),
        validate_default=True,
        validation_alias="QDRANT_LOCAL_PATH",
        description="Каталог локального Qdrant (режим local)",
    )
    qdrant_collection: str = Field(
        default="guideline_chunks",
        validation_alias="QDRANT_COLLECTION",
        description="База имени коллекции чанков: размерность дописывается кодом",
    )

    @field_validator("qdrant_local_path")
    @classmethod
    def _anchor_qdrant_path(cls, value: Path) -> Path:
        """Относительный путь считать от ``backend/``, а не от текущего каталога."""
        return value if value.is_absolute() else BACKEND_DIR / value

    @property
    def sqlalchemy_url(self) -> str:
        """DSN для SQLAlchemy; явная ошибка, если подключение не сконфигурировано."""
        if self.database_url is None:
            raise DatabaseNotConfiguredError("DATABASE_URL is not set")
        return self.database_url
