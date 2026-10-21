"""Эндпоинты черновика врачебного протокола."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.routers.dependencies import get_runtime
from app.runtime import Runtime
from app.schemas.protocol import ProtocolDraftRequest, ProtocolDraftResponse
from app.services.guidelines import GuidelineNotFoundError
from app.services.protocols import (
    GuidelineNotReadyError,
    ProtocolFormError,
    ProtocolService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/protocols", tags=["protocols"])


def get_protocol_service(runtime: Annotated[Runtime, Depends(get_runtime)]) -> ProtocolService:
    """Сервис протоколов: работает поверх сервиса клинреков из рантайма."""
    return ProtocolService(runtime.guidelines)


@router.post(
    "/validate",
    response_model=ProtocolDraftResponse,
    summary="Проверить черновик протокола",
    responses={
        400: {"description": "Форма не прошла проверку; в причине названо поле"},
        404: {"description": "Клинрек или указанная версия не найдены"},
        409: {"description": "Клинрек не готов к проверке"},
    },
)
def validate_protocol(
    service: Annotated[ProtocolService, Depends(get_protocol_service)],
    draft: ProtocolDraftRequest,
) -> ProtocolDraftResponse:
    """Проверить форму, подтвердить клинрек и вернуть атомарные пункты.

    Ничего не сохраняет: идентификатора протокола в ответе нет, черновик живёт только в
    интерфейсе. Это первый шаг проверки — сама проверка на соответствие клинреку появится
    следующим изменением.

    Обработчик объявлен синхронным: чтение метаданных клинрека блокирующее, и FastAPI
    выполнит его в рабочем потоке.
    """
    try:
        return service.validate(draft)
    except ProtocolFormError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GuidelineNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
