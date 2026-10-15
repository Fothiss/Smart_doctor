"""Чанкинг клинрека: абзацы → секции → чанки с геометрией подсветки.

Модуль чистый: на вход страницы со строками, на выход готовые чанки. Ни диска, ни
настроек, ни FastAPI — поэтому проверяется тестами на синтетических страницах.

Замеры на реальном клинреке (220 страниц), на которых основаны решения:

- межстрочный интервал 21 pt, межабзацный 41 pt — абзац отделяется порогом
  ``1.4 × медиана``;
- длина абзаца p50 = 118 символов, p90 = 2192: абзац — неделимая единица, но не
  единица чанка, половина абзацев короче 200 символов;
- размер шрифта у всего текста одинаков (12 pt), зато различается гарнитура:
  тело — ``TimesNewRomanPSMT``, заголовки — ``TimesNewRomanPS-BoldMT``;
- заголовок и следующий за ним текст разделены обычным межстрочным интервалом,
  поэтому заголовок определяется по строке, а не по абзацу: иначе он склеивается
  с телом и перестаёт быть коротким.
"""

import re
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha1
from itertools import pairwise
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas.chunk import BBox, Chunk, ChunkRect
from app.services.pdf_text import MIN_PAGE_CHARS, Line, PageText

CHUNK_NAMESPACE = uuid5(NAMESPACE_URL, "smart-doctor/guideline-chunk")
"""Пространство имён идентификаторов чанков: детерминировано и не зависит от запуска."""

PARAGRAPH_GAP_FACTOR = 1.4
"""Во сколько раз разрыв должен превышать медианный, чтобы считаться новым абзацем."""

MAX_HEADING_CHARS = 120
"""Заголовок короче этого предела; всё длиннее — обычный текст."""

MIN_TOC_LEADER_LINES = 3
"""Сколько строк с точечными выносками делают страницу оглавлением."""

BOLD_FONT_MARKER = "bold"
"""Признак полужирной гарнитуры в имени шрифта (``TimesNewRomanPS-BoldMT``)."""

_DOT_LEADER = re.compile(r"\.{5,}")
_PAGE_NUMBER = re.compile(r"^[-–—\s]*\d{1,4}[-–—\s]*$")
_NUMBERED_HEADING = re.compile(r"^\d{1,2}(?:\.\d{1,2})+\.?(?:\s|$)|^\d{1,2}\.\s+[А-ЯЁA-Z]")
"""Номер раздела: многоуровневый (``2.4``) либо одноуровневый с точкой и заглавной буквой.

Одно число без точки (``4 Диагностика``) заголовком не считается: так выглядят строки
таблиц, и их в клинреке сотни.
"""
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_ABBREVIATIONS = (
    "рис.",
    "табл.",
    "см.",
    "стр.",
    "т.е.",
    "т.д.",
    "т.п.",
    "др.",
    "г.",
    "гг.",
    "мг.",
    "мл.",
    "мм.",
)


@dataclass(frozen=True)
class ChunkingParams:
    """Размеры чанка в символах.

    Целевой размер — середина, к которой сливаются соседние абзацы; максимум —
    предел, после которого абзац режется по границам предложений.
    """

    target_chars: int = 800
    min_chars: int = 300
    max_chars: int = 1500
    overlap_chars: int = 150


@dataclass(frozen=True)
class Paragraph:
    """Абзац: подряд идущие строки, не разделённые увеличенным разрывом."""

    lines: tuple[Line, ...]

    @property
    def text(self) -> str:
        """Текст абзаца одной строкой."""
        return " ".join(line.text for line in self.lines)

    def _dominant(self, key_of: Callable[[Line], str | float]) -> str | float:
        """Значение, которым набрана большая часть абзаца по числу символов."""
        weights: dict[str | float, int] = {}
        for line in self.lines:
            key = key_of(line)
            weights[key] = weights.get(key, 0) + len(line.text)
        if not weights:
            return ""
        return max(weights.items(), key=lambda item: item[1])[0]

    @property
    def font(self) -> str:
        """Гарнитура абзаца."""
        return str(self._dominant(lambda line: line.font))

    @property
    def size(self) -> float:
        """Размер шрифта абзаца."""
        return float(self._dominant(lambda line: line.size))


@dataclass(frozen=True)
class Block:
    """Абзац вместе с признаком того, что это заголовок секции."""

    paragraph: Paragraph
    is_heading: bool


@dataclass(frozen=True)
class Unit:
    """Неделимый кусок текста внутри секции: абзац или часть разорванного абзаца."""

    text: str
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Section:
    """Секция клинрека: заголовок и следующие за ним куски текста."""

    title: str | None
    units: tuple[Unit, ...]


def _is_service_line(text: str) -> bool:
    """Служебная строка: выноска оглавления или номер страницы."""
    return bool(_DOT_LEADER.search(text)) or bool(_PAGE_NUMBER.match(text))


def _is_service_page(page: PageText, min_chars: int) -> bool:
    """Служебная страница: титул, вкладка-картинка или страница оглавления."""
    if page.chars < min_chars:
        return True
    leaders = sum(1 for line in page.lines if _DOT_LEADER.search(line.text))
    return leaders >= MIN_TOC_LEADER_LINES


def content_lines(pages: Sequence[PageText], min_page_chars: int = MIN_PAGE_CHARS) -> list[Line]:
    """Строки документа без служебных страниц и строк."""
    return [
        line
        for page in pages
        if not _is_service_page(page, min_page_chars)
        for line in page.lines
        if not _is_service_line(line.text)
    ]


def dominant_font(lines: Sequence[Line]) -> str:
    """Гарнитура, которой набрана большая часть текста: тело документа."""
    weights: dict[str, int] = {}
    for line in lines:
        weights[line.font] = weights.get(line.font, 0) + len(line.text)
    if not weights:
        return ""
    return max(weights.items(), key=lambda item: item[1])[0]


def is_heading_line(line: Line, body_font: str = "") -> bool:
    """Похожа ли строка на заголовок секции.

    Сигнал один — нумерация вида ``2.4`` у короткой строки. Ни размер шрифта, ни
    гарнитура не годятся: кегль у всего текста одинаков, полужирным набраны шапки
    таблиц (их в клинреке сотни), а курсив составляет заметную часть тела. Номер
    раздела — единственный признак, который структуру документа отражает.
    """
    text = line.text.strip()
    if not text or len(text) > MAX_HEADING_CHARS:
        return False
    if text.endswith((";", ",")):
        return False
    return bool(_NUMBERED_HEADING.match(text))


def paragraphs_from_pages(
    pages: Sequence[PageText], min_page_chars: int = MIN_PAGE_CHARS
) -> list[Paragraph]:
    """Собрать абзацы из страниц, отбросив служебный текст.

    Строки склеиваются, пока вертикальный разрыв не превысит ``1.4 × медиана``:
    на замеренном документе это 41 pt против 21 pt, то есть абзац отделяется
    устойчиво и без анализа шрифта.
    """
    lines = content_lines(pages, min_page_chars)
    if not lines:
        return []

    gaps = [
        previous.top - current.top
        for previous, current in pairwise(lines)
        if previous.page == current.page and previous.top > current.top
    ]
    threshold = PARAGRAPH_GAP_FACTOR * statistics.median(gaps) if gaps else 0.0

    paragraphs: list[Paragraph] = []
    current: list[Line] = []
    for line in lines:
        if current:
            previous = current[-1]
            same_page = previous.page == line.page
            if not same_page or previous.top - line.top > threshold:
                paragraphs.append(Paragraph(tuple(current)))
                current = []
        current.append(line)
    if current:
        paragraphs.append(Paragraph(tuple(current)))
    return paragraphs


def blocks_from_paragraphs(paragraphs: Sequence[Paragraph], body_font: str) -> list[Block]:
    """Разделить абзацы на заголовки и обычный текст.

    Заголовок и следующий за ним текст разделены обычным межстрочным интервалом,
    поэтому граница проходит по строке: блок заголовка закрывается, как только
    встречается строка обычной гарнитуры.
    """
    blocks: list[Block] = []
    current: list[Line] = []
    current_heading = False

    def flush() -> None:
        if current:
            blocks.append(Block(paragraph=Paragraph(tuple(current)), is_heading=current_heading))

    for paragraph in paragraphs:
        for line in paragraph.lines:
            heading = is_heading_line(line, body_font)
            if current and heading != current_heading:
                flush()
                current = []
            current_heading = heading
            current.append(line)
    flush()
    return blocks


def sections_from_blocks(
    blocks: Sequence[Block], params: ChunkingParams | None = None
) -> list[Section]:
    """Разложить блоки по секциям: заголовок открывает новую секцию.

    Заголовок остаётся первым куском своей секции, поэтому он попадает в текст
    первого чанка и одновременно доступен в метаданных как ``section``.
    """
    resolved = params or ChunkingParams()
    sections: list[Section] = []
    title: str | None = None
    units: list[Unit] = []

    for block in blocks:
        if block.is_heading:
            if units or title is not None:
                sections.append(Section(title=title, units=tuple(units)))
            title = block.paragraph.text.strip()
            units = [Unit(text=title, lines=block.paragraph.lines)]
            continue
        units.extend(_units_from_paragraphs([block.paragraph], resolved))

    if units or title is not None:
        sections.append(Section(title=title, units=tuple(units)))
    return sections


def split_sentences(text: str) -> list[str]:
    """Разбить текст на предложения, не разрывая общепринятые сокращения."""
    parts = _SENTENCE_END.split(text)
    sentences: list[str] = []
    for part in parts:
        if sentences and sentences[-1].lower().endswith(_ABBREVIATIONS):
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _lines_for_range(lines: Sequence[Line], start: int, end: int) -> tuple[Line, ...]:
    """Строки, попадающие в диапазон символов абзаца.

    Смещения считаются по тому же склеенному тексту, что и у абзаца, поэтому
    прямоугольники подсветки соответствуют именно этой части текста.
    """
    result: list[Line] = []
    cursor = 0
    for line in lines:
        line_end = cursor + len(line.text)
        if cursor < end and line_end > start:
            result.append(line)
        cursor = line_end + 1
    return tuple(result)


def _split_long_sentence(sentence: str, budget: int) -> list[str]:
    """Разрезать предложение длиннее предела по словам.

    Без этого максимальный размер чанка не соблюсти: в клинреках встречаются
    перечисления одним предложением на пару тысяч символов.
    """
    if len(sentence) <= budget:
        return [sentence]
    parts: list[str] = []
    current = ""
    for word in sentence.split():
        if current and len(current) + len(word) + 1 > budget:
            parts.append(current)
            current = word
            continue
        current = f"{current} {word}".strip()
    if current:
        parts.append(current)
    return parts


def _split_paragraph(paragraph: Paragraph, params: ChunkingParams) -> list[Unit]:
    """Разрезать длинный абзац по границам предложений.

    Каждая следующая часть начинается с последнего предложения предыдущей, если оно
    помещается: перекрытие появляется только там, где абзац разорван, и не дублирует
    текст на границе абзацев.
    """
    sentences = split_sentences(paragraph.text)
    if not sentences:
        return [Unit(text=paragraph.text, lines=paragraph.lines)]

    budget = max(params.min_chars, params.max_chars - params.overlap_chars)
    pieces: list[str] = []
    for sentence in sentences:
        pieces.extend(_split_long_sentence(sentence, budget))

    units: list[Unit] = []
    buffer: list[str] = []
    length = 0
    offset = 0
    start_offset = 0

    for piece in pieces:
        if buffer and length + len(piece) + 1 > budget:
            text = " ".join(buffer)
            units.append(
                Unit(text=text, lines=_lines_for_range(paragraph.lines, start_offset, offset))
            )
            tail = buffer[-1]
            start_offset = max(0, offset - len(tail))
            buffer = [tail] if len(tail) + len(piece) + 1 <= budget else []
            length = sum(len(item) + 1 for item in buffer)
        buffer.append(piece)
        length += len(piece) + 1
        offset += len(piece) + 1

    if buffer:
        text = " ".join(buffer)
        units.append(Unit(text=text, lines=_lines_for_range(paragraph.lines, start_offset, offset)))
    return units


def _units_from_paragraphs(paragraphs: Sequence[Paragraph], params: ChunkingParams) -> list[Unit]:
    """Развернуть абзацы в неделимые куски: короткие целиком, длинные — по предложениям."""
    units: list[Unit] = []
    for paragraph in paragraphs:
        if len(paragraph.text) <= params.max_chars:
            units.append(Unit(text=paragraph.text, lines=paragraph.lines))
        else:
            units.extend(_split_paragraph(paragraph, params))
    return units


def _merge_units(units: Sequence[Unit], params: ChunkingParams) -> list[Unit]:
    """Слить соседние куски в чанки целевого размера, не превышая максимум."""
    chunks: list[Unit] = []
    buffer: list[Unit] = []
    length = 0

    for unit in units:
        fits = length + len(unit.text) + 1 <= params.max_chars
        if buffer and (not fits or length >= params.target_chars):
            text = " ".join(item.text for item in buffer)
            lines = tuple(line for item in buffer for line in item.lines)
            chunks.append(Unit(text=text, lines=lines))
            buffer = []
            length = 0
        buffer.append(unit)
        length += len(unit.text) + 1

    if buffer:
        text = " ".join(item.text for item in buffer)
        lines = tuple(line for item in buffer for line in item.lines)
        chunks.append(Unit(text=text, lines=lines))
    return chunks


def _rects(lines: Sequence[Line]) -> list[ChunkRect]:
    """Объединить строки чанка в прямоугольник на каждую страницу."""
    boxes: dict[int, BBox] = {}
    order: list[int] = []
    for line in lines:
        box = line.bbox
        current = boxes.get(line.page)
        if current is None:
            boxes[line.page] = box
            order.append(line.page)
            continue
        boxes[line.page] = (
            min(current[0], box[0]),
            min(current[1], box[1]),
            max(current[2], box[2]),
            max(current[3], box[3]),
        )
    return [ChunkRect(page=page, bbox=boxes[page]) for page in order]


def chunk_id_for(guideline_id: UUID, version: int, lines: Sequence[Line], text: str) -> UUID:
    """Детерминированный идентификатор чанка.

    Зависит от клинрека, версии, позиции первой строки и хеша текста, но не от времени
    индексации: повторный прогон даёт те же идентификаторы, поэтому ссылки в уже
    выданных отчётах остаются рабочими.
    """
    first = lines[0]
    position = f"{first.page}:{first.top:.1f}"
    digest = sha1(text.encode("utf-8")).hexdigest()
    return uuid5(CHUNK_NAMESPACE, f"{guideline_id}|{version}|{position}|{digest}")


def build_chunks(
    pages: Sequence[PageText],
    guideline_id: UUID,
    version: int,
    params: ChunkingParams | None = None,
    min_page_chars: int = MIN_PAGE_CHARS,
) -> list[Chunk]:
    """Собрать чанки клинрека: страницы → абзацы → секции → чанки.

    Границы страниц при нарезке не учитываются: чанк режется по смыслу, а страницы
    становятся прямоугольниками подсветки (их может быть несколько).
    """
    params = params or ChunkingParams()
    lines = content_lines(pages, min_page_chars)
    if not lines:
        return []

    paragraphs = paragraphs_from_pages(pages, min_page_chars)
    body_font = dominant_font(lines)
    blocks = blocks_from_paragraphs(paragraphs, body_font)

    chunks: list[Chunk] = []
    for section in sections_from_blocks(blocks, params):
        for unit in _merge_units(section.units, params):
            unit_lines = unit.lines
            if not unit_lines:
                continue
            rects = _rects(unit_lines)
            chunks.append(
                Chunk(
                    chunk_id=chunk_id_for(guideline_id, version, unit_lines, unit.text),
                    guideline_id=guideline_id,
                    guideline_version=version,
                    section=section.title,
                    text=unit.text,
                    chunk_index=len(chunks),
                    page=rects[0].page,
                    bbox=rects[0].bbox,
                    rects=rects,
                )
            )
    return chunks
