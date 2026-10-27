"""Проверки чтения настроек: алиасы полей, приоритет окружения, якоря путей."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    BACKEND_DIR,
    PROJECT_ROOT,
    BackendSettings,
    ChatSettings,
    DatabaseNotConfiguredError,
    DatabaseSettings,
    EmbeddingSettings,
    LLMProvider,
    LLMSettings,
    QdrantMode,
    Settings,
    StructuredMethod,
)

SETTINGS_DOMAINS = (BackendSettings, DatabaseSettings, LLMSettings, ChatSettings, EmbeddingSettings)

COMPOSE_ONLY_VARS = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_PORT",
    "BACKEND_PORT",
    "FRONTEND_PORT",
}
"""Переменные корневого ``.env``: их читает Docker Compose, а не backend."""


def _field_aliases() -> dict[str, str]:
    """Пары «поле → переменная окружения» по всем доменам настроек."""
    return {
        f"{model.__name__}.{name}": alias
        for model in SETTINGS_DOMAINS
        for name, field in model.model_fields.items()
        if isinstance(alias := field.validation_alias, str)
    }


def _declared_env_names() -> set[str]:
    """Имена переменных окружения, объявленные в ``validation_alias``."""
    return set(_field_aliases().values())


def _example_env_names() -> set[str]:
    """Имена переменных из ``.env.example``."""
    lines = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    names = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        names.add(stripped.split("=", 1)[0].strip())
    return names


def test_every_field_declares_env_alias() -> None:
    """У каждого поля явный ``validation_alias`` — иначе переменная неочевидна."""
    missing = [
        f"{model.__name__}.{name}"
        for model in SETTINGS_DOMAINS
        for name, field in model.model_fields.items()
        if not isinstance(field.validation_alias, str)
    ]

    assert missing == [], f"поля без validation_alias: {missing}"


def test_env_aliases_are_unique_and_upper_snake() -> None:
    """Алиасы — уникальные имена переменных в верхнем регистре."""
    aliases = _field_aliases()

    assert len(set(aliases.values())) == len(aliases), f"дубли переменных: {aliases}"
    not_upper = {field: alias for field, alias in aliases.items() if alias != alias.upper()}
    assert not_upper == {}, f"алиасы не в верхнем регистре: {not_upper}"


def test_env_example_has_no_unreadable_variables() -> None:
    """Опечатка в .env.example не должна молча превращаться в дефолт кода."""
    unknown = _example_env_names() - _declared_env_names() - COMPOSE_ONLY_VARS

    assert unknown == set(), f"переменные не читаются приложением: {sorted(unknown)}"


def test_every_documented_variable_is_covered() -> None:
    """Обратная проверка: каждая переменная настроек описана в .env.example."""
    backend_vars = _declared_env_names() - {"APP_NAME", "APP_VERSION"}

    assert backend_vars <= _example_env_names()


def test_host_binds_loopback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST", raising=False)

    assert BackendSettings(_env_file=None).host == "127.0.0.1"


def test_env_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "5")

    settings = BackendSettings(_env_file=None)

    assert settings.host == "0.0.0.0"
    assert settings.max_upload_size_mb == 5
    assert settings.max_upload_size_bytes == 5 * 1024 * 1024


def test_settings_are_built_from_arguments(tmp_path: Path) -> None:
    """populate_by_name: настройки собираются по имени поля, без окружения."""
    settings = BackendSettings(storage_dir=tmp_path, max_upload_size_mb=1)

    assert settings.storage_dir == tmp_path
    assert settings.max_upload_size_bytes == 1024 * 1024


def test_storage_dir_is_anchored_to_backend_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Относительный STORAGE_DIR не должен зависеть от текущего каталога запуска."""
    monkeypatch.setenv("STORAGE_DIR", "probe-storage")

    settings = BackendSettings(_env_file=None)

    assert settings.storage_dir == BACKEND_DIR / "probe-storage"
    assert settings.guidelines_dir == BACKEND_DIR / "probe-storage" / "guidelines"


def test_storage_dir_absolute_path_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    assert BackendSettings(_env_file=None).storage_dir == tmp_path


def test_database_url_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """DSN с паролем не хранится в коде: без переменной настройка пуста."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    database = DatabaseSettings(_env_file=None)

    assert database.database_url is None
    with pytest.raises(DatabaseNotConfiguredError, match="DATABASE_URL is not set"):
        _ = database.sqlalchemy_url


def test_database_url_is_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = "postgresql+psycopg://user:secret@db:5432/smart_doctor"
    monkeypatch.setenv("DATABASE_URL", dsn)

    assert DatabaseSettings(_env_file=None).sqlalchemy_url == dsn


def test_llm_provider_is_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")

    assert LLMSettings(_env_file=None).llm_provider is LLMProvider.DEEPSEEK

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None)


def test_llm_keys_are_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIGACHAT_TOKEN", "super-secret-key")

    llm = LLMSettings(_env_file=None)

    assert llm.gigachat_token is not None
    assert llm.gigachat_token.get_secret_value() == "super-secret-key"
    assert "super-secret-key" not in repr(llm)
    assert llm.gigachat_configured is True


def test_llm_defaults_match_gigachat_client() -> None:
    """Дефолты клиента: Ultra для ответа, лёгкая модель для переписывания, TLS выключен."""
    llm = LLMSettings(_env_file=None)

    assert llm.gigachat_base_url == "https://api.giga.chat/v1"
    assert llm.gigachat_model == "GigaChat-3-Ultra"
    assert llm.gigachat_rewrite_model == "GigaChat-2"
    assert llm.gigachat_structured_method is StructuredMethod.FUNCTION_CALLING
    assert llm.gigachat_verify_ssl_certs is False
    assert llm.gigachat_timeout > 0
    assert llm.gigachat_configured is False


def test_unknown_structured_method_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Неизвестный способ structured output роняет старт, а не подменяется молча."""
    monkeypatch.setenv("GIGACHAT_STRUCTURED_METHOD", "tools")

    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None)


def test_ca_bundle_path_is_anchored_to_backend_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Относительный путь сертификата не зависит от текущего каталога запуска."""
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE_FILE", "certs/russian_trusted_root_ca.pem")

    llm = LLMSettings(_env_file=None)

    assert llm.gigachat_ca_bundle_file == BACKEND_DIR / "certs" / "russian_trusted_root_ca.pem"


def test_chat_defaults_keep_context_and_window_bounded() -> None:
    """Параметры чата: топ-8, окно 4 сообщения, порог близости выключен."""
    chat = ChatSettings(_env_file=None)

    assert (chat.top_k, chat.history_window) == (8, 4)
    assert chat.max_guidelines == 5
    assert chat.max_context_chars == 12000
    assert chat.min_score == 0.0


def test_domains_are_composable(tmp_path: Path) -> None:
    """Настройки собираются в тесте по частям — без переменных окружения."""
    settings = Settings(
        backend=BackendSettings(storage_dir=tmp_path, max_upload_size_mb=1),
        database=DatabaseSettings(database_url=None),
        llm=LLMSettings(llm_provider=LLMProvider.GIGACHAT),
    )

    assert settings.backend.guidelines_dir == tmp_path / "guidelines"
    assert settings.backend.max_upload_size_bytes == 1024 * 1024
    assert settings.database.database_url is None


def test_qdrant_defaults_to_local_mode(tmp_path: Path) -> None:
    """По умолчанию векторное хранилище локальное: контейнеры не нужны."""
    database = DatabaseSettings(qdrant_local_path=tmp_path / "qdrant")

    assert database.qdrant_mode is QdrantMode.LOCAL
    assert database.qdrant_local_path == tmp_path / "qdrant"
    assert database.qdrant_collection == "guideline_chunks"


def test_qdrant_local_path_is_anchored_to_backend_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Относительный путь хранилища не зависит от текущего каталога запуска."""
    monkeypatch.setenv("QDRANT_LOCAL_PATH", "probe-qdrant")

    assert DatabaseSettings(_env_file=None).qdrant_local_path == BACKEND_DIR / "probe-qdrant"


def test_unknown_qdrant_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Неизвестный режим хранилища роняет старт, а не откатывается к локальному."""
    monkeypatch.setenv("QDRANT_MODE", "cluster")

    with pytest.raises(ValidationError):
        DatabaseSettings(_env_file=None)


def test_chunk_sizes_must_be_consistent() -> None:
    """Несогласованные размеры чанка отвергаются: минимум ≤ цель ≤ максимум."""
    with pytest.raises(ValidationError, match="min <= target <= max"):
        BackendSettings(chunk_min_chars=900, chunk_target_chars=800, chunk_max_chars=1500)

    settings = BackendSettings(chunk_min_chars=100, chunk_target_chars=200, chunk_max_chars=300)

    assert (settings.chunk_min_chars, settings.chunk_target_chars) == (100, 200)


def test_embedding_defaults_target_local_directory(tmp_path: Path) -> None:
    """Модель эмбеддингов по умолчанию — локальная папка, а не идентификатор BERTA."""
    settings = EmbeddingSettings(ml_models_dir=tmp_path)

    assert settings.dimension == 1024
    assert settings.model_id == "Qwen/Qwen3-Embedding-0.6B"
    assert settings.model_dir == tmp_path / "Qwen3-Embedding-0.6B"


def test_embedding_query_prefix_is_single() -> None:
    """Префикс запроса формируется одним механизмом."""
    settings = EmbeddingSettings(query_instruction="Retrieve a fragment")

    assert settings.query_prefix.count("Instruct:") == 1
    assert settings.query_prefix.endswith("Query:")
