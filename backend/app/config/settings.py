"""Настройки приложения, читаются из переменных окружения."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация сервиса."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Smart Doctor API"
    app_version: str = "0.1.0"

    # Локально 127.0.0.1; в контейнере HOST=0.0.0.0 задаёт Dockerfile
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Хранилище PDF клинреков — локальная ФС (см. README)
    storage_dir: Path = Path("storage")
    max_upload_size_mb: int = 50

    # Локальный запуск без контейнеров: хосты compose переопределяются в docker-compose.yml
    database_url: str = "postgresql+psycopg://smart_doctor:smart_doctor@localhost:5432/smart_doctor"
    qdrant_url: str = "http://localhost:6333"

    @property
    def guidelines_dir(self) -> Path:
        """Каталог загруженных клинреков."""
        return self.storage_dir / "guidelines"

    @property
    def max_upload_size_bytes(self) -> int:
        """Ограничение размера загружаемого файла в байтах."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Единственный экземпляр настроек."""
    return Settings()


settings = get_settings()
