"""Проверки клиента эмбеддингов: комплект файлов модели и формат запроса."""

from pathlib import Path

import numpy as np
import pytest

from app.clients.embeddings import (
    EmbeddingError,
    SentenceTransformerEmbedder,
    ensure_model_files,
    resolve_device,
)
from app.config import EmbeddingSettings


def _complete_model(directory: Path) -> Path:
    """Папка с обязательными файлами модели."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text("{}", encoding="utf-8")
    (directory / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (directory / "model.safetensors").write_bytes(b"weights")
    return directory


def test_missing_directory_is_reported(tmp_path: Path) -> None:
    """Отсутствие папки модели даёт понятную причину."""
    with pytest.raises(EmbeddingError, match="not found"):
        ensure_model_files(tmp_path / "absent")


def test_incomplete_model_is_reported(tmp_path: Path) -> None:
    """Неполный комплект файлов не проходит проверку."""
    directory = tmp_path / "model"
    directory.mkdir()
    (directory / "config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(EmbeddingError, match="incomplete"):
        ensure_model_files(directory)


def test_complete_model_is_accepted(tmp_path: Path) -> None:
    """Полный комплект файлов проходит проверку."""
    directory = _complete_model(tmp_path / "model")

    assert ensure_model_files(directory) == directory


def test_query_prefix_is_added_once(tmp_path: Path) -> None:
    """Запрос получает ровно один префикс, документы — ни одного.

    Двойной префикс не падает и не логируется: он просто тихо ухудшает поиск,
    поэтому проверяется отдельно.
    """
    settings = EmbeddingSettings(
        ml_models_dir=tmp_path,
        model_path=Path("model"),
        query_instruction="Retrieve a fragment",
    )
    embedder = SentenceTransformerEmbedder(settings)
    seen: list[list[str]] = []

    def fake_encode(texts: list[str], **_: object) -> np.ndarray:
        seen.append(list(texts))
        # sentence-transformers возвращает матрицу, у строк есть .tolist()
        return np.zeros((len(texts), settings.dimension))

    embedder._model = type("Model", (), {"encode": staticmethod(fake_encode)})()

    embedder.encode_documents(["фрагмент клинрека"])
    embedder.encode_query("жалобы пациента")

    assert seen[0] == ["фрагмент клинрека"]
    assert seen[1] == ["Instruct: Retrieve a fragment\nQuery: жалобы пациента"]
    assert seen[1][0].count("Instruct:") == 1


def test_query_prefix_uses_settings() -> None:
    """Префикс собирается из инструкции и не содержит второго механизма промпта."""
    settings = EmbeddingSettings(query_instruction="Find the guideline fragment")

    assert settings.query_prefix == "Instruct: Find the guideline fragment\nQuery:"


def test_model_dir_resolves_relative_path(tmp_path: Path) -> None:
    """Относительный путь модели считается от каталога моделей."""
    settings = EmbeddingSettings(ml_models_dir=tmp_path, model_path=Path("Qwen3-Embedding-0.6B"))

    assert settings.model_dir == tmp_path / "Qwen3-Embedding-0.6B"


def test_auto_device_prefers_cuda_when_available() -> None:
    """`auto` берёт видеокарту: на CPU эмбеддинг идёт десятки минут, на GPU — секунды."""
    assert resolve_device("auto", cuda_available=True) == "cuda"
    assert resolve_device("auto", cuda_available=False) == "cpu"


def test_explicit_device_wins_over_availability() -> None:
    """Явное устройство не переопределяется: контейнер без GPU должен считать на CPU."""
    assert resolve_device("cpu", cuda_available=True) == "cpu"
    assert resolve_device("CUDA", cuda_available=False) == "cuda"
    assert resolve_device(" auto ", cuda_available=True) == "cuda"


def test_device_is_configurable(tmp_path: Path) -> None:
    """Устройство приходит из настроек, по умолчанию — auto."""
    assert EmbeddingSettings(ml_models_dir=tmp_path).device == "auto"
    assert EmbeddingSettings(ml_models_dir=tmp_path, device="cpu").device == "cpu"
