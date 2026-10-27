"""Проверки рантайма: ленивый клиент LLM и безопасное закрытие."""

from app.clients.llm import GigaChatClient
from app.config import Settings
from app.runtime import Runtime


def test_llm_is_created_lazily(settings: Settings) -> None:
    """Клиент LLM не создаётся, пока его не спросили: экраны работают без ключа."""
    runtime = Runtime(settings)

    assert runtime._llm is None
    client = runtime.llm
    assert isinstance(client, GigaChatClient)
    assert runtime._llm is client


def test_close_without_dependencies_does_not_fail(settings: Settings) -> None:
    """Закрытие рантайма без открытых хранилища и клиента не поднимает ошибок."""
    runtime = Runtime(settings)

    runtime.close()

    assert runtime._llm is None
    assert runtime._store is None


def test_close_releases_llm(settings: Settings) -> None:
    """После закрытия клиент LLM отпускается: он не переживает lifespan приложения."""
    runtime = Runtime(settings)
    client = runtime.llm

    runtime.close()

    assert client is not None
    assert runtime._llm is None
