"""Эндпоинты клинреков."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response

from app.clients.vector_store import VectorStoreError
from app.routers.dependencies import get_guideline_service, get_runtime
from app.runtime import Runtime
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.guidelines import (
    DuplicateGuidelineError,
    GuidelineNotFoundError,
    GuidelineService,
    GuidelineTooLargeError,
    InvalidGuidelineError,
)
from app.services.icd import InvalidIcdCodeError, normalize_codes
from app.services.indexing import IndexingError, IndexingInProgressError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guidelines", tags=["guidelines"])

UPLOAD_CHUNK_SIZE = 1024 * 1024
"""Размер порции чтения загрузки: PDF не поднимается в память целиком."""

__all__ = ["get_guideline_service", "router"]


async def _read_chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    """Отдавать тело multipart-загрузки порциями."""
    while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
        yield chunk


async def _index_in_background(
    runtime: Runtime, service: GuidelineService, guideline_id: UUID
) -> None:
    """Проиндексировать клинрек, не роняя фоновую задачу.

    Причину отказа сервис записывает в статус клинрека; здесь логируется только то,
    что до статуса не дошло — например, клинрек успели удалить.
    """
    try:
        await runtime.indexer.index(service, guideline_id)
    except IndexingError as exc:
        logger.warning("Indexing was not started: %s", exc)


def _normalize_icd_filter(icd: str | None) -> str | None:
    """Нормализовать код из фильтра списка; пустой фильтр — это отсутствие фильтра."""
    if icd is None or not icd.strip():
        return None
    try:
        codes = normalize_codes([icd])
    except InvalidIcdCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return codes[0]


@router.post(
    "",
    response_model=Guideline,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить PDF клинических рекомендаций",
    responses={
        400: {"description": "Файл пустой или не PDF, либо нет ни одного кода МКБ"},
        409: {"description": "PDF с таким содержимым уже загружен"},
        413: {"description": "Файл превышает допустимый размер"},
    },
)
async def upload_guideline(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF клинических рекомендаций")],
    title: Annotated[str | None, Form(description="Название клинрека")] = None,
    icd_codes: Annotated[
        list[str] | None, Form(description="Коды МКБ-10; хотя бы один обязателен")
    ] = None,
) -> Guideline:
    """Принять PDF, сохранить в хранилище и вернуть метаданные клинрека.

    Индексация запускается после ответа: разбор PDF и эмбеддинги занимают минуты, и
    держать на них HTTP-запрос нельзя.

    Поле ``icd_codes`` объявлено необязательным на уровне FastAPI только ради кода
    ответа: отсутствие кодов — это `400` с причиной, а не автоматический `422` от
    валидации параметров.
    """
    try:
        guideline = await service.create(
            _read_chunks(file), file.filename or "", title, icd_codes=icd_codes or []
        )
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

    background.add_task(_index_in_background, runtime, service, guideline.guideline_id)
    return guideline


@router.get(
    "",
    response_model=list[Guideline],
    summary="Список клинреков",
    responses={
        422: {"description": "Некорректные query-параметры или код МКБ вне формата"},
    },
)
async def list_guidelines(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    guideline_status: Annotated[
        GuidelineStatus | None, Query(alias="status", description="Фильтр по состоянию")
    ] = None,
    icd: Annotated[
        str | None, Query(description="Фильтр по коду МКБ-10, например I10")
    ] = None,
    limit: Annotated[int, Query(ge=1, description="Размер страницы")] = 50,
    offset: Annotated[int, Query(ge=0, description="Смещение")] = 0,
) -> list[Guideline]:
    """Вернуть клинреки для экрана Library, свежие загрузки первыми."""
    return list(service.list(guideline_status, limit, offset, _normalize_icd_filter(icd)))


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


@router.delete(
    "/{guideline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Удалить клинрек",
    responses={
        404: {"description": "Клинрек не найден"},
        409: {"description": "По клинреку идёт индексация"},
        503: {"description": "Векторное хранилище недоступно"},
    },
)
async def delete_guideline(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    guideline_id: Annotated[UUID, Path(description="Идентификатор клинрека")],
) -> Response:
    """Удалить клинрек вместе с оригиналом PDF и его фрагментами.

    Обработчик синхронный: удаление чанков в Qdrant блокирующее, и FastAPI выполнит его
    в рабочем потоке, не останавливая цикл событий.
    """
    try:
        runtime.delete_guideline(guideline_id)
    except GuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IndexingInProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{guideline_id}/index",
    response_model=Guideline,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить индексацию клинрека",
    responses={
        404: {"description": "Клинрек не найден"},
        409: {"description": "Индексация этого клинрека уже идёт"},
    },
)
async def index_guideline(
    service: Annotated[GuidelineService, Depends(get_guideline_service)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
    background: BackgroundTasks,
    guideline_id: Annotated[UUID, Path(description="Идентификатор клинрека")],
) -> Guideline:
    """Поставить клинрек в обработку и запустить индексацию в фоне.

    Повтор нужен после отказа: без него клинрек в ``failed`` остаётся необработанным
    навсегда, и его фрагменты нельзя процитировать.
    """
    try:
        service.get(guideline_id)
    except GuidelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if runtime.indexer.is_running(guideline_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"indexing is already running for guideline {guideline_id}",
        )

    queued = runtime.indexer.mark_queued(service, guideline_id)
    background.add_task(_index_in_background, runtime, service, guideline_id)
    return queued
