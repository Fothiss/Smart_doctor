"""Схемы чата по клинрекам.

Схемы описывают только структуру. Правила содержимого — непустой вопрос, допустимое
число документов, готовность клинрека — проверяет сервис, чтобы отказ приходил как `400`
с причиной, а не как автоматический `422` от валидации тела запроса.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChunkRef(BaseModel):
    """Ссылка на фрагмент в предыдущем ответе ассистента.

    Принимается ради того, чтобы клиент мог присылать ленту как есть. В контекст
    прошлые цитаты не попадают: ответ строится только по найденным сейчас фрагментам.
    """

    chunk_id: UUID


class ChatMessage(BaseModel):
    """Сообщение ленты, которое присылает интерфейс."""

    role: Literal["user", "assistant"] = Field(description="Кто написал сообщение")
    text: str = Field(description="Текст сообщения")
    citations: list[ChunkRef] = Field(
        default_factory=list, description="Ссылки предыдущего ответа; сервером не используются"
    )


class ChatAskRequest(BaseModel):
    """Вопрос врача по выбранным клинрекам."""

    guideline_ids: list[UUID] = Field(
        default_factory=list, description="Клинреки, по которым разрешено искать"
    )
    question: str = Field(default="", description="Вопрос целиком, без опоры на историю")
    history: list[ChatMessage] = Field(
        default_factory=list, description="Лента диалога: влияет только на поисковый запрос"
    )


class ChatStatus(StrEnum):
    """Чем закончился вопрос."""

    ANSWERED = "answered"
    NOT_FOUND = "not_found"


class Citation(BaseModel):
    """Подтверждённая ссылка на фрагмент клинрека."""

    n: int = Field(ge=1, description="Номер фрагмента, на который ссылается ответ")
    chunk_id: UUID
    guideline_id: UUID
    guideline_version: int = Field(ge=1, description="Версия документа на момент индексации")
    guideline_title: str
    section: str | None = Field(default=None, description="Заголовок раздела клинрека")
    page: int = Field(ge=1, description="Страница первого прямоугольника фрагмента")
    quote: str = Field(min_length=1, description="Дословная цитата из фрагмента")


class SearchInfo(BaseModel):
    """Какой запрос ушёл в поиск и что с ним сделало переписывание."""

    expression: str = Field(description="Текст поискового запроса")
    rewritten: bool = Field(description="False — использована склейка с прошлым вопросом")
    constraints_lost: int = Field(
        ge=0, description="Сколько условий вопроса не попало в переписанный запрос"
    )


class ChatGuidelineRef(BaseModel):
    """Документ, по которому шёл поиск."""

    guideline_id: UUID
    title: str
    version: int = Field(ge=1)


class ChatAnswer(BaseModel):
    """Ответ чата: либо текст со ссылками, либо отказ «не найдено»."""

    status: ChatStatus
    answer: str | None = Field(default=None, description="Текст ответа с маркерами [n]")
    citations: list[Citation] = Field(
        default_factory=list, description="Только подтверждённые ссылки"
    )
    search: SearchInfo
    searched_guidelines: list[ChatGuidelineRef] = Field(default_factory=list)
