"""Свод настроек бэкенда."""

from functools import lru_cache

from app.config.base_settings import BackendSettings
from app.config.database import DatabaseSettings
from app.config.llm import LLMSettings


class Settings:
    """Настройки бэкенда, разложенные по доменам.

    Домены независимы: каждый читает только свои переменные окружения, поэтому
    в тесте подсистему можно собрать отдельно от остальных.
    """

    def __init__(
        self,
        backend: BackendSettings | None = None,
        database: DatabaseSettings | None = None,
        llm: LLMSettings | None = None,
    ) -> None:
        self.backend = backend if backend is not None else BackendSettings()
        self.database = database if database is not None else DatabaseSettings()
        self.llm = llm if llm is not None else LLMSettings()


@lru_cache
def get_settings() -> Settings:
    """Единственный экземпляр настроек — зависимость FastAPI."""
    return Settings()
