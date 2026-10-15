"""Схемы фрагмента клинрека: текст цитаты и геометрия её подсветки."""

from uuid import UUID

from pydantic import BaseModel, Field

BBox = tuple[float, float, float, float]
"""Прямоугольник в системе координат страницы PDF: левая, нижняя, правая, верхняя."""


class ChunkRect(BaseModel):
    """Прямоугольник подсветки на одной странице."""

    page: int = Field(ge=1, description="Страница PDF, начиная с 1")
    bbox: BBox = Field(description="Границы фрагмента на этой странице")


class Chunk(BaseModel):
    """Фрагмент клинрека: цитата и адрес, по которому её видно в оригинале.

    Прямоугольников может быть несколько: чанк режется по смыслу и не обязан
    укладываться в одну страницу, а подсветить его нужно целиком.
    """

    chunk_id: UUID
    guideline_id: UUID
    guideline_version: int = Field(ge=1, description="Версия документа на момент чанкинга")
    section: str | None = Field(default=None, description="Заголовок раздела клинрека")
    text: str = Field(min_length=1, description="Текст фрагмента — цитата в вердикте")
    chunk_index: int = Field(ge=0, description="Порядковый номер чанка в документе")
    page: int = Field(ge=1, description="Страница первого прямоугольника")
    bbox: BBox | None = Field(default=None, description="Первый прямоугольник подсветки")
    rects: list[ChunkRect] = Field(
        default_factory=list, description="По прямоугольнику на каждую страницу фрагмента"
    )
