"""Базовые настройки бэкенда: чтение окружения и собственные параметры сервиса."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
"""Корень ``backend/`` — от него считаются пути по умолчанию."""

PROJECT_ROOT = BACKEND_DIR.parent
"""Корень репозитория."""

ENV_FILES = (PROJECT_ROOT / ".env", BACKEND_DIR / ".env")
"""Файлы окружения в порядке возрастания приоритета: побеждает ``backend/.env``.

Пути считаются от этого файла, а не от текущего каталога: запуск из любого места
читает одни и те же ``.env``. Раньше пути были относительными и при запуске
из другого каталога молча не находились — настройки откатывались к дефолтам кода.
"""


class BaseEnvSettings(BaseSettings):
    """Общее чтение окружения для настроек бэкенда.

    ``extra="ignore"`` — вынужденная мера: корневой ``.env`` общий с Docker Compose
    (``POSTGRES_*``, ``BACKEND_PORT``, ``FRONTEND_PORT``), а ``extra="forbid"`` уронил бы
    чтение этих файлов. От опечаток защищают ``validation_alias`` у каждого поля и
    ``tests/test_settings.py``: он сверяет ``.env.example`` с объявленными алиасами.

    ``populate_by_name=True`` — настройки можно собрать и аргументами по имени поля,
    а не только переменными окружения: так их подменяют тесты и DI.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


class BackendSettings(BaseEnvSettings):
    """Собственные настройки бэкенда: HTTP-сервер, логи, хранилище клинреков."""

    app_name: str = Field(
        default="Smart Doctor API",
        validation_alias="APP_NAME",
        description="Название сервиса в OpenAPI",
    )
    app_version: str = Field(
        default="0.1.0",
        validation_alias="APP_VERSION",
        description="Версия приложения в /health",
    )

    # Локально bind на loopback; в контейнере HOST=0.0.0.0 задаёт Dockerfile
    host: str = Field(
        default="127.0.0.1",
        validation_alias="HOST",
        description="Адрес bind HTTP-сервера",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias="PORT",
        description="Порт HTTP-сервера",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Уровень логирования",
    )

    storage_dir: Path = Field(
        default=Path("storage"),
        validate_default=True,
        validation_alias="STORAGE_DIR",
        description="Каталог PDF и метаданных клинреков",
    )
    max_upload_size_mb: int = Field(
        default=50,
        ge=1,
        validation_alias="MAX_UPLOAD_SIZE_MB",
        description="Лимит размера загружаемого PDF",
    )

    @field_validator("storage_dir")
    @classmethod
    def _anchor_storage_dir(cls, value: Path) -> Path:
        """Относительный путь считать от ``backend/``, а не от текущего каталога."""
        return value if value.is_absolute() else BACKEND_DIR / value

    @property
    def guidelines_dir(self) -> Path:
        """Каталог загруженных клинреков."""
        return self.storage_dir / "guidelines"

    @property
    def max_upload_size_bytes(self) -> int:
        """Ограничение размера загружаемого файла в байтах."""
        return self.max_upload_size_mb * 1024 * 1024
