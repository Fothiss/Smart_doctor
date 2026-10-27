"""Эндпоинты чата по выбранным клинрекам."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.clients.llm import LLMError
from app.clients.vector_store import VectorStoreError
from app.routers.dependencies import get_runtime
from app.runtime import Runtime
from app.schemas.chat import ChatAnswer, ChatAskRequest
from app.services.chat import (
    ChatGuidelineNotFoundError,
    ChatGuidelineNotReadyError,
    ChatRequestError,
    ChatService,
)
from app.services.query_rewrite import QueryRewriter
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_chat_service(runtime: Annotated[Runtime, Depends(get_runtime)]) -> ChatService:
    """Собрать сервис чата поверх долгоживущих зависимостей рантайма.

    Сервис собирается на запрос: он лёгкий и держит только ссылки на модель
    эмбеддингов, векторное хранилище и клиент LLM, которые уже созданы один раз.
    """
    chat = runtime.settings.chat
    return ChatService(
        guidelines=runtime.guidelines,
        retrieval=RetrievalService(
            runtime.embedder,
            runtime.store,
            top_k=chat.top_k,
            max_context_chars=chat.max_context_chars,
            min_score=chat.min_score,
        ),
        rewriter=QueryRewriter(runtime.llm, window=chat.history_window),
        llm=runtime.llm,
        settings=chat,
    )


@router.post(
    "/ask",
    response_model=ChatAnswer,
    summary="Ответить на вопрос по выбранным клинрекам",
    responses={
        400: {"description": "Пустой вопрос, нет документов или их слишком много"},
        404: {"description": "Клинрек не найден"},
        409: {"description": "Клинрек не готов отвечать на вопросы"},
        502: {"description": "LLM недоступна или отказала"},
        503: {"description": "Векторное хранилище недоступно"},
    },
)
async def ask(
    service: Annotated[ChatService, Depends(get_chat_service)],
    request: ChatAskRequest,
) -> ChatAnswer:
    """Ответить по фрагментам выбранных клинреков.

    Обработчик асинхронный: поиск уходит в рабочий поток внутри сервиса, а вызов модели
    ждёт сеть, не занимая цикл событий.
    """
    try:
        return await service.ask(request)
    except ChatRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ChatGuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ChatGuidelineNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
