"""Эндпоинты фрагментов клинрека."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.clients.vector_store import VectorStoreError
from app.routers.dependencies import get_runtime
from app.runtime import Runtime
from app.schemas.chunk import Chunk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chunks", tags=["chunks"])


@router.get(
    "/{chunk_id}",
    response_model=Chunk,
    summary="Фрагмент клинрека по идентификатору",
    responses={
        404: {"description": "Фрагмент не найден"},
        503: {"description": "Векторное хранилище недоступно"},
    },
)
def get_chunk(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    chunk_id: Annotated[UUID, Path(description="Идентификатор фрагмента из вердикта")],
) -> Chunk:
    """Вернуть текст цитаты и прямоугольники её подсветки в оригинале.

    Обработчик объявлен синхронным: чтение из векторного хранилища блокирующее, и
    FastAPI выполняет его в рабочем потоке, не останавливая цикл событий.
    """
    try:
        chunk = runtime.store.get(chunk_id)
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"chunk {chunk_id} not found"
        )
    return chunk
