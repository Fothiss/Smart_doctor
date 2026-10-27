"""Настройки чата по клинрекам: размер контекста и окно истории.

Вынесены отдельно от ``llm``: провайдер и ключи меняются по другим причинам, чем
бюджет контекста, и подменяются в тестах независимо.
"""

from pydantic import Field

from app.config.base_settings import BaseEnvSettings


class ChatSettings(BaseEnvSettings):
    """Сколько фрагментов и сколько истории получает каждый вопрос.

    ``top_k`` больше обычного для RAG не случайно: модели дешевле выкинуть лишний
    фрагмент, чем не заметить отсутствие нужного, а второго поиска в этом изменении нет.

    ``min_score`` по умолчанию 0, то есть порог выключен: масштаб косинусных оценок
    выбранной модели эмбеддингов не измерен, и включённый вслепую порог отсекал бы
    верные ответы.
    """

    top_k: int = Field(
        default=8,
        ge=1,
        le=50,
        validation_alias="CHAT_TOP_K",
        description="Сколько фрагментов попадает в контекст модели",
    )
    max_context_chars: int = Field(
        default=12000,
        ge=500,
        validation_alias="CHAT_MAX_CONTEXT_CHARS",
        description="Бюджет контекста в символах: слабые фрагменты отбрасываются",
    )
    max_guidelines: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias="CHAT_MAX_GUIDELINES",
        description="Предел выбранных клинреков в одном вопросе",
    )
    history_window: int = Field(
        default=4,
        ge=0,
        le=20,
        validation_alias="CHAT_HISTORY_WINDOW",
        description="Сколько последних сообщений влияет на поисковый запрос",
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        validation_alias="CHAT_MIN_SCORE",
        description="Порог близости фрагмента; 0 — отключён",
    )
