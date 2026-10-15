"""Настройки локальной модели эмбеддингов.

Файлы модели лежат в отдельной папке (``ML_MODELS_DIR``) и в репозиторий не попадают:
веса не хранятся в git, но и не скачиваются из сети при каждом запуске — индексация
работает офлайн.
"""

from pathlib import Path

from pydantic import Field, field_validator

from app.config.base_settings import BACKEND_DIR, BaseEnvSettings

DEFAULT_MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
"""Модель эмбеддингов по умолчанию: 1024 измерения, 32K контекста, apache-2.0."""

DEFAULT_MODEL_DIRNAME = "Qwen3-Embedding-0.6B"
"""Имя папки модели внутри ``ML_MODELS_DIR``."""


def default_threads() -> int:
    """Столько потоков брать по умолчанию, если считать на CPU.

    Одно ядро остаётся HTTP-серверу, иначе во время индексации API перестаёт отвечать.
    """
    import os

    return max(1, (os.cpu_count() or 4) - 1)


class EmbeddingSettings(BaseEnvSettings):
    """Локальная модель эмбеддингов и параметры инференса.

    Размерность объявлена явно: она сверяется с коллекцией векторного хранилища,
    и расхождение обязано падать ошибкой, а не подставлять чужие векторы.
    """

    model_id: str = Field(
        default=DEFAULT_MODEL_ID,
        validation_alias="EMBEDDING_MODEL",
        description="Идентификатор модели: попадает в метаданные клинрека",
    )
    ml_models_dir: Path = Field(
        default=Path("ml_models"),
        validate_default=True,
        validation_alias="ML_MODELS_DIR",
        description="Каталог с папками моделей эмбеддингов",
    )
    model_path: Path = Field(
        default=Path(DEFAULT_MODEL_DIRNAME),
        validation_alias="EMBEDDING_MODEL_PATH",
        description="Папка модели внутри ML_MODELS_DIR либо абсолютный путь",
    )
    dimension: int = Field(
        default=1024,
        ge=1,
        validation_alias="EMBEDDING_DIM",
        description="Размерность вектора: сверяется с коллекцией Qdrant",
    )
    max_seq_length: int = Field(
        default=512,
        ge=1,
        validation_alias="EMBEDDING_MAX_SEQ_LENGTH",
        description="Максимальная длина входа: ограничивает память на длинном чанке",
    )
    batch_size: int = Field(
        default=8,
        ge=1,
        validation_alias="EMBEDDING_BATCH_SIZE",
        description="Сколько чанков кодируется за один проход",
    )
    query_instruction: str = Field(
        default=(
            "Given a clinical protocol statement, retrieve the clinical guideline "
            "fragment that covers it"
        ),
        validation_alias="EMBEDDING_QUERY_INSTRUCTION",
        description="Инструкция для запросов: документы кодируются без неё",
    )
    threads: int = Field(
        default_factory=default_threads,
        ge=1,
        validation_alias="EMBEDDING_THREADS",
        description="Потоки инференса на CPU: остаток ядер остаётся HTTP-серверу",
    )
    device: str = Field(
        default="auto",
        validation_alias="EMBEDDING_DEVICE",
        description="Устройство инференса: auto (cuda, если доступна), cpu, cuda",
    )

    @field_validator("ml_models_dir")
    @classmethod
    def _anchor_ml_models_dir(cls, value: Path) -> Path:
        """Относительный путь считать от ``backend/``, а не от текущего каталога."""
        return value if value.is_absolute() else BACKEND_DIR / value

    @property
    def model_dir(self) -> Path:
        """Абсолютный путь к папке с файлами модели."""
        if self.model_path.is_absolute():
            return self.model_path
        return self.ml_models_dir / self.model_path

    @property
    def query_prefix(self) -> str:
        """Префикс запроса — единственный механизм формирования запроса.

        Документы кодируются без него. Второй механизм (``prompt_name="query"``)
        использовать нельзя: два префикса склеятся и качество поиска просядет молча.
        """
        return f"Instruct: {self.query_instruction}\nQuery:"
