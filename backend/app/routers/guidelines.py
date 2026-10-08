"""Эндпоинты клинреков."""

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.guidelines import (
    DuplicateGuidelineError,
    GuidelineNotFoundError,
    GuidelineService,
    GuidelineTooLargeError,
    InvalidGuidelineError,
)

router = APIRouter(prefix="/api/guidelines", tags=["guidelines"])

UPLOAD_CHUNK_SIZE = 1024 * 1024
"""Размер порции чтения загрузки: PDF не поднимается в память целиком."""


async def _read_chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    """Отдавать тело multipart-загрузки порциями."""
    while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
        yield chunk


def get_guideline_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GuidelineService:
    """Собрать сервис клинреков из настроек — провайдер зависимостей API-слоя."""
    return GuidelineService(
        guidelines_dir=settings.backend.guidelines_dir,
        max_upload_size_bytes=settings.backend.max_upload_size_bytes,
    )


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
        return await service.create(_read_chunks(file), file.filename or "", title)
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


@router.get(
    "",
    response_model=list[Guideline],
    summary="Список клинреков",
    responses={422: {"description": "Некорректные query-параметры"}},
)
async def list_guidelines(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    guideline_status: Annotated[
        GuidelineStatus | None, Query(alias="status", description="Фильтр по состоянию")
    ] = None,
    limit: Annotated[int, Query(ge=1, description="Размер страницы")] = 50,
    offset: Annotated[int, Query(ge=0, description="Смещение")] = 0,
) -> list[Guideline]:
    """Вернуть клинреки для экрана Library, свежие загрузки первыми."""
    return list(service.list(guideline_status, limit, offset))


@router.get(
    "/{guideline_id}",
    response_model=Guideline,
    summary="Метаданные клинрека",
    responses={404: {"description": "Клинрек не найден"}},
)
async def get_guideline(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    guideline_id: Annotated[UUID, Path(description="Идентификатор клинрека")],
) -> Guideline:
    """Вернуть метаданные и статус индексации одного клинрека."""
    try:
        return service.get(guideline_id)
    except GuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{guideline_id}/file",
    response_class=FileResponse,
    summary="Оригинальный PDF клинрека",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF-поток"},
        404: {"description": "Клинрек или указанная версия не найдены"},
    },
)
async def get_guideline_file(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    guideline_id: Annotated[UUID, Path(description="Идентификатор клинрека")],
    version: Annotated[
        int | None, Query(ge=1, description="Версия документа; по умолчанию последняя")
    ] = None,
) -> FileResponse:
    """Отдать PDF для PDF.js; Range обрабатывает ``FileResponse``."""
    try:
        guideline, pdf_path = service.get_pdf(guideline_id, version)
    except GuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=guideline.filename,
        content_disposition_type="inline",
    )
