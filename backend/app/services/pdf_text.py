"""Извлечение текста и геометрии страниц PDF.

Модуль отдаёт страницы как набор строк с координатами: этого достаточно, чтобы собрать
абзацы, секции и прямоугольники подсветки для PDF.js. Координаты приводятся к системе
страницы PDF (начало координат в левом нижнем углу) — именно её ожидает
``viewport.convertToViewportPoint`` во фронтенде.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from app.schemas.chunk import BBox

MIN_PAGE_CHARS = 40
"""Страница с меньшим объёмом текста считается служебной: титул или вкладка-картинка."""

MIN_AVG_CHARS_PER_PAGE = 40
"""Средний объём текста на страницу ниже порога означает PDF без текстового слоя."""


class PdfTextError(Exception):
    """PDF не удалось прочитать."""


class MissingTextLayerError(PdfTextError):
    """В PDF нет текстового слоя: нужен OCR, чанкинг по пустому тексту невозможен."""


@dataclass(frozen=True)
class Line:
    """Строка страницы: текст, прямоугольник в системе PDF, размер и гарнитура шрифта."""

    text: str
    page: int
    x0: float
    x1: float
    bottom: float
    top: float
    size: float
    font: str

    @property
    def bbox(self) -> BBox:
        """Прямоугольник строки в системе координат страницы."""
        return (self.x0, self.bottom, self.x1, self.top)

    @property
    def height(self) -> float:
        """Высота строки: по ней различаются межстрочный и межабзацный интервалы."""
        return self.top - self.bottom


@dataclass(frozen=True)
class PageText:
    """Текст одной страницы PDF."""

    number: int
    width: float
    height: float
    lines: tuple[Line, ...]
    rotation: int = 0
    """Угол поворота страницы: координаты строк приведены к неразвёрнутой странице."""

    @property
    def chars(self) -> int:
        """Сколько символов текста на странице."""
        return sum(len(line.text) for line in self.lines)


def _dominant(chars: Sequence[dict]) -> tuple[float, str]:
    """Размер и гарнитура, которыми набрана большая часть строки."""
    if not chars:
        return 0.0, ""
    sizes: dict[float, int] = {}
    fonts: dict[str, int] = {}
    for char in chars:
        size = round(float(char.get("size", 0.0)), 1)
        sizes[size] = sizes.get(size, 0) + 1
        font = str(char.get("fontname", ""))
        fonts[font] = fonts.get(font, 0) + 1
    size = max(sizes.items(), key=lambda item: item[1])[0]
    font = max(fonts.items(), key=lambda item: item[1])[0]
    return size, font


def _unrotated_box(
    rotation: int,
    x0: float,
    x1: float,
    top: float,
    bottom: float,
    width: float,
    height: float,
) -> BBox:
    """Привести прямоугольник строки к системе координат неразвёрнутой страницы.

    pdfplumber отдаёт координаты уже развёрнутой страницы (``top``/``bottom`` от
    верхнего края), а PDF.js в ``convertToViewportPoint`` ждёт координаты страницы
    без поворота. Соответствие выведено и проверено на фикстуре с ``/Rotate 90``:
    текст, поставленный в ``(72, 770)``, возвращается в те же координаты.
    """
    if rotation == 90:
        return (top, x0, bottom, x1)
    if rotation == 180:
        return (width - x1, height - bottom, width - x0, height - top)
    if rotation == 270:
        return (width - bottom, height - x1, width - top, height - x0)
    return (x0, height - bottom, x1, height - top)


def _lines_from_page(page: pdfplumber.page.Page, number: int) -> Iterator[Line]:
    """Разложить страницу на строки, приводя координаты к системе PDF.

    Размеры неразвёрнутой страницы для повёрнутых страниц берутся обратно: у них
    pdfplumber меняет ширину и высоту местами.
    """
    rotation = int(page.rotation or 0) % 360
    width = float(page.width)
    height = float(page.height)
    if rotation in (90, 270):
        width, height = height, width

    for raw in page.extract_text_lines(return_chars=True):
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        size, font = _dominant(raw.get("chars") or [])
        bbox = _unrotated_box(
            rotation,
            float(raw["x0"]),
            float(raw["x1"]),
            float(raw["top"]),
            float(raw["bottom"]),
            width,
            height,
        )
        yield Line(
            text=text,
            page=number,
            x0=bbox[0],
            x1=bbox[2],
            bottom=bbox[1],
            top=bbox[3],
            size=size,
            font=font,
        )


def iter_pages(path: Path) -> Iterator[PageText]:
    """Прочитать PDF постранично, закрывая страницу сразу после обработки.

    Страница не удерживается в памяти: клинрек на 220 страниц иначе занял бы её
    целиком вместе с разобранным содержимым.
    """
    try:
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                try:
                    rotation = int(page.rotation or 0) % 360
                    width = float(page.width)
                    height = float(page.height)
                    if rotation in (90, 270):
                        width, height = height, width
                    lines = tuple(_lines_from_page(page, number))
                    yield PageText(
                        number=number,
                        width=width,
                        height=height,
                        lines=lines,
                        rotation=rotation,
                    )
                finally:
                    page.close()
    except PdfTextError:
        raise
    except Exception as exc:
        raise PdfTextError(f"failed to read PDF: {exc}") from exc


def read_pages(path: Path) -> list[PageText]:
    """Прочитать все страницы PDF."""
    return list(iter_pages(path))


def ensure_text_layer(pages: Sequence[PageText]) -> None:
    """Проверить, что в PDF есть текстовый слой.

    Скан без распознавания даёт пустые страницы: молча записать такой документ как
    проиндексированный значит обещать врачу цитаты, которых нет.
    """
    if not pages:
        raise MissingTextLayerError("PDF has no pages")
    total = sum(page.chars for page in pages)
    if total < MIN_AVG_CHARS_PER_PAGE * len(pages):
        raise MissingTextLayerError(
            "PDF has no text layer: scanning requires OCR, which is not supported"
        )
