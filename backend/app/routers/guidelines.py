"""Эндпоинты клинреков."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.schemas.guideline import Guideline
from app.services.guidelines import (
    DuplicateGuidelineError,
    GuidelineService,
    GuidelineTooLargeError,
    InvalidGuidelineError,
    get_guideline_service,
)

router = APIRouter(prefix="/api/guidelines", tags=["guidelines"])


@router.post(
    "",
    response_model=Guideline,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить PDF клинических рекомендаций",
    responses={
        400: {"description": "Файл пустой или не PDF"},
        409: {"description": "PDF с таким содержимым уже загружен"},
        413: {"description": "Файл превышает допустимый размер"},
    },
)
async def upload_guideline(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    file: Annotated[UploadFile, File(description="PDF клинических рекомендаций")],
    title: Annotated[str | None, Form(description="Название клинрека")] = None,
) -> Guideline:
    """Принять PDF, сохранить в хранилище и вернуть метаданные клинрека."""
    try:
        return await service.create(file, title)
    except InvalidGuidelineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except GuidelineTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except DuplicateGuidelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "guideline with the same content already exists",
                "guideline_id": str(exc.guideline.guideline_id),
            },
        ) from exc
