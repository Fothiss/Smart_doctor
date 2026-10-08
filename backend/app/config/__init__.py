"""Конфигурация бэкенда, разложенная по доменам.

Настройки берутся только через ``get_settings()`` (FastAPI-зависимость) или
``create_app(settings)``: глобального объекта настроек нет, чтобы домены
не тянули конфигурацию напрямую.

- ``base_settings`` — базовое чтение окружения и собственные настройки бэкенда
- ``database`` — PostgreSQL и Qdrant
- ``llm`` — провайдер LLM и embeddings
"""

from app.config.base_settings import (
    BACKEND_DIR,
    PROJECT_ROOT,
    BackendSettings,
    BaseEnvSettings,
)
from app.config.database import DatabaseNotConfiguredError, DatabaseSettings
from app.config.llm import LLMProvider, LLMSettings
from app.config.settings import Settings, get_settings

__all__ = [
    "BACKEND_DIR",
    "PROJECT_ROOT",
    "BackendSettings",
    "BaseEnvSettings",
    "DatabaseNotConfiguredError",
    "DatabaseSettings",
    "LLMProvider",
    "LLMSettings",
    "Settings",
    "get_settings",
]
