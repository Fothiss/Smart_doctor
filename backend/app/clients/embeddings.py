"""Клиент локальной модели эмбеддингов.

Модель лежит в локальной папке и держится в памяти процесса: индексация работает
офлайн, без обращения к Hugging Face. Тяжёлые импорты (``torch``, ``sentence_transformers``)
выполняются при первой загрузке, чтобы обычный запуск API без индексации не платил
за них временем старта.
"""

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from app.config.embedding import EmbeddingSettings

logger = logging.getLogger(__name__)

REQUIRED_MODEL_FILES = ("config.json", "tokenizer_config.json")
"""Файлы, без которых модель не собрать осмысленно."""

WEIGHTS_FILES = ("model.safetensors", "pytorch_model.bin")
"""Веса модели: подходит любой из форматов."""

DEVICE_AUTO = "auto"
"""Значение `EMBEDDING_DEVICE`, при котором устройство выбирается по доступности CUDA."""


class EmbeddingError(Exception):
    """Модель недоступна, неполна или не смогла посчитать вектор."""


def resolve_device(preference: str, cuda_available: bool) -> str:
    """Выбрать устройство инференса.

    `auto` берёт видеокарту, если сборка PyTorch её видит: на CPU эмбеддинг 0.6B-модели
    идёт десятки минут, на GPU — секунды. Явное `cpu` нужно там, где GPU нет (контейнер)
    или она занята.
    """
    normalized = preference.strip().lower()
    if normalized == DEVICE_AUTO:
        return "cuda" if cuda_available else "cpu"
    return normalized


def _embedding_dimension(transformer: object) -> int:
    """Размерность эмбеддинга: имя метода менялось между версиями sentence-transformers."""
    try:
        getter = transformer.get_embedding_dimension  # type: ignore[attr-defined]
    except AttributeError:
        getter = transformer.get_word_embedding_dimension  # type: ignore[attr-defined]
    return int(getter())


class Embedder(Protocol):
    """Интерфейс эмбеддера: индексации и будущему поиску нужен только он."""

    @property
    def dimension(self) -> int:
        """Размерность вектора."""
        ...

    @property
    def model_id(self) -> str:
        """Идентификатор модели: попадает в метаданные клинрека."""
        ...

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Посчитать векторы фрагментов клинрека."""
        ...

    def encode_query(self, text: str) -> list[float]:
        """Посчитать вектор поискового запроса."""
        ...


def ensure_model_files(model_dir: Path) -> Path:
    """Проверить комплект файлов модели и вернуть путь к папке.

    Неполный снапшот — не мелочь: без конфигурации пулинга sentence-transformers
    молча применит усреднение вместо последнего токена и выдаст «валидные», но
    неверные векторы. Поэтому проверка явная и падает с понятной причиной.
    """
    if not model_dir.is_dir():
        raise EmbeddingError(f"embedding model not found: {model_dir}")
    missing = [name for name in REQUIRED_MODEL_FILES if not (model_dir / name).is_file()]
    if not any((model_dir / name).is_file() for name in WEIGHTS_FILES):
        missing.append(" or ".join(WEIGHTS_FILES))
    if missing:
        raise EmbeddingError(
            f"embedding model is incomplete at {model_dir}: missing {', '.join(missing)}"
        )
    return model_dir


class SentenceTransformerEmbedder:
    """Эмбеддер на sentence-transformers.

    Qwen3-Embedding — декодерная модель: пулинг по последнему токену, паддинг слева,
    а инструкция добавляется только запросу. Модули собираются явно, а не берутся из
    конфигурации папки, чтобы результат не зависел от полноты снапшота.
    """

    def __init__(self, settings: EmbeddingSettings) -> None:
        self._settings = settings
        self._model: object | None = None

    @property
    def dimension(self) -> int:
        """Размерность вектора из настроек."""
        return self._settings.dimension

    @property
    def model_id(self) -> str:
        """Идентификатор модели из настроек."""
        return self._settings.model_id

    def _load(self) -> object:
        """Загрузить модель один раз за время жизни процесса."""
        if self._model is not None:
            return self._model

        model_dir = ensure_model_files(self._settings.model_dir)
        import torch
        from sentence_transformers import SentenceTransformer, models

        device = resolve_device(self._settings.device, torch.cuda.is_available())
        if device == "cpu":
            # Потоки имеет смысл настраивать только на CPU: на GPU считает видеокарта
            torch.set_num_threads(self._settings.threads)
        logger.info("Embedding model device: %s", device)

        transformer = models.Transformer(
            str(model_dir), max_seq_length=self._settings.max_seq_length
        )
        pooling = models.Pooling(
            _embedding_dimension(transformer), pooling_mode="lasttoken"
        )
        model = SentenceTransformer(modules=[transformer, pooling], device=device)
        # Последний токен при right-padding оказался бы pad-токеном
        model.tokenizer.padding_side = "left"
        self._model = model
        return model

    def _encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Посчитать векторы и нормализовать их под косинусную метрику."""
        model = self._load()
        try:
            vectors = model.encode(  # type: ignore[attr-defined]
                list(texts),
                batch_size=self._settings.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"failed to encode text: {exc}") from exc
        return [vector.tolist() for vector in vectors]

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Кодировать документы: инструкция к ним не добавляется."""
        return self._encode(texts)

    def encode_query(self, text: str) -> list[float]:
        """Кодировать запрос: инструкция добавляется ровно один раз."""
        return self._encode([f"{self._settings.query_prefix} {text}"])[0]
