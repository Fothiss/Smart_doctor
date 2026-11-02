"""Конфигурация бэкенда, разложенная по доменам.

Настройки берутся только через ``get_settings()`` (FastAPI-зависимость) или
``create_app(settings)``: глобального объекта настроек нет, чтобы домены
не тянули конфигурацию напрямую.

- ``base_settings`` — базовое чтение окружения и собственные настройки бэкенда
- ``database`` — PostgreSQL и Qdrant
- ``gigachat`` — доступ к GigaChat API: ключ, scope, адрес, TLS, повторы
- ``llm`` — провайдер LLM, модели чата и переписывания запроса
- ``chat`` — параметры чата по клинрекам
- ``embedding`` — модель эмбеддингов GigaChat
"""

from app.config.base_settings import (
    BACKEND_DIR,
    PROJECT_ROOT,
    BackendSettings,
    BaseEnvSettings,
)
from app.config.chat import ChatSettings
from app.config.database import DatabaseNotConfiguredError, DatabaseSettings, QdrantMode
from app.config.embedding import DEFAULT_DIMENSION, DEFAULT_MODEL_ID, EmbeddingSettings
from app.config.gigachat import GigaChatSettings
from app.config.llm import LLMProvider, LLMSettings, StructuredMethod
from app.config.settings import Settings, get_settings

__all__ = [
    "BACKEND_DIR",
    "DEFAULT_DIMENSION",
    "DEFAULT_MODEL_ID",
    "PROJECT_ROOT",
    "BackendSettings",
    "BaseEnvSettings",
    "ChatSettings",
    "DatabaseNotConfiguredError",
    "DatabaseSettings",
    "EmbeddingSettings",
    "GigaChatSettings",
    "LLMProvider",
    "LLMSettings",
    "QdrantMode",
    "Settings",
    "StructuredMethod",
    "get_settings",
]
