"""Проверки чанкинга: абзацы, секции, границы чанков, геометрия, идентификаторы."""

from dataclasses import replace
from itertools import pairwise
from uuid import uuid4

from app.services.chunking import (
    ChunkingParams,
    blocks_from_paragraphs,
    build_chunks,
    chunk_id_for,
    is_heading_line,
    paragraphs_from_pages,
    sections_from_blocks,
    split_sentences,
)
from app.services.pdf_text import Line, PageText

GUIDELINE_ID = uuid4()
LINE_GAP = 16.0
PARAGRAPH_GAP = 40.0


def _line(text: str, page: int = 1, top: float = 700.0, font: str = "Body") -> Line:
    """Строка с предсказуемой геометрией."""
    return Line(
        text=text,
        page=page,
        x0=72.0,
        x1=72.0 + len(text) * 5,
        bottom=top - 10.0,
        top=top,
        size=12.0,
        font=font,
    )


def _page(number: int, lines: list[Line], height: float = 842.0) -> PageText:
    """Страница с заданными строками.

    Номер страницы проставляется строкам: в реальном документе строка всегда знает свою
    страницу, и подсветка опирается именно на это. Иначе строки разных страниц
    схлопываются в один прямоугольник, и тест молча проверяет не то, что нужно.
    """
    stamped = tuple(line if line.page == number else replace(line, page=number) for line in lines)
    return PageText(number=number, width=595.0, height=height, lines=stamped)


def _sequential(
    *texts: str, page: int = 1, start: float = 700.0, step: float = LINE_GAP
) -> PageText:
    """Страница, где строки идут подряд с одинаковым интервалом."""
    lines = [
        _line(text, page=page, top=start - index * step) for index, text in enumerate(texts)
    ]
    return _page(page, lines)


def test_paragraph_splits_on_large_gap() -> None:
    """Строки склеиваются в абзац, пока разрыв обычный, и расходятся на увеличенном."""
    page = _page(
        1,
        [
            _line("Первая строка абзаца", top=700.0),
            _line("вторая строка того же абзаца", top=700.0 - LINE_GAP),
            _line("первая строка нового абзаца", top=700.0 - LINE_GAP - PARAGRAPH_GAP),
        ],
    )

    paragraphs = paragraphs_from_pages([page])

    assert [paragraph.text for paragraph in paragraphs] == [
        "Первая строка абзаца вторая строка того же абзаца",
        "первая строка нового абзаца",
    ]


def test_paragraph_does_not_span_pages() -> None:
    """Абзац не продолжается через границу страницы."""
    pages = [
        _page(1, [_line("конец страницы", page=1)]),
        _page(2, [_line("начало страницы", page=2)]),
    ]

    # Порог служебной страницы снижен: в синтетической странице одна короткая строка,
    # и проверяем мы именно границу страницы, а не отбрасывание служебного текста
    paragraphs = paragraphs_from_pages(pages, min_page_chars=1)

    assert len(paragraphs) == 2


def test_numbered_line_opens_section() -> None:
    """Нумерованный заголовок открывает новую секцию, обычный абзац — нет."""
    page = _sequential(
        "1. Определение",
        "Текст определения.",
        "1.1 Этиология",
        "Текст этиологии.",
    )

    blocks = blocks_from_paragraphs(paragraphs_from_pages([page]), "Body")
    sections = sections_from_blocks(blocks)

    assert [section.title for section in sections] == ["1. Определение", "1.1 Этиология"]
    assert all(section.units for section in sections)


def test_plain_line_is_not_a_heading() -> None:
    """Строка без номера раздела заголовком не считается, даже если она короткая."""
    assert not is_heading_line(_line("Краткая информация"))
    assert not is_heading_line(_line("4 Диагностика"))
    assert is_heading_line(_line("2.4. Оценка риска"))


def test_chunk_does_not_mix_sections() -> None:
    """Ни один чанк не содержит текст двух секций."""
    page = _sequential(
        "1. Определение",
        "Определение описано здесь достаточно подробно.",
        "2. Диагностика",
        "Диагностика описана здесь достаточно подробно.",
    )

    chunks = build_chunks([page], GUIDELINE_ID, 1, ChunkingParams(target_chars=200, max_chars=400))

    assert chunks
    for chunk in chunks:
        titles = [title for title in ("1. Определение", "2. Диагностика") if title in chunk.text]
        assert len(set(titles)) <= 1
        assert chunk.section == (titles[0] if titles else chunk.section)


def test_long_paragraph_is_split_by_sentences() -> None:
    """Длинный абзац режется по границам предложений и не превышает максимум."""
    sentences = [f"Предложение номер {index} про диагностику и лечение." for index in range(40)]
    page = _page(1, [_line(" ".join(sentences), top=700.0)])
    params = ChunkingParams(target_chars=400, min_chars=200, max_chars=500, overlap_chars=100)

    chunks = build_chunks([page], GUIDELINE_ID, 1, params)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= params.max_chars
        assert chunk.text.strip().endswith(".")
        assert chunk.text[0].isupper()


def test_overlap_appears_only_inside_split_paragraph() -> None:
    """Перекрытие есть на разрыве абзаца и отсутствует между абзацами."""
    long_text = " ".join(f"Длинное предложение {index}." for index in range(30))
    page = _page(
        1,
        [
            _line(long_text, top=700.0),
            _line("Короткий отдельный абзац.", top=700.0 - 60),
        ],
    )
    params = ChunkingParams(target_chars=300, min_chars=150, max_chars=400, overlap_chars=80)

    chunks = build_chunks([page], GUIDELINE_ID, 1, params)
    parts = [chunk for chunk in chunks if "Длинное предложение" in chunk.text]

    assert len(parts) > 1
    # Соседние части разорванного абзаца перекрываются последним предложением
    for previous, following in pairwise(parts):
        last_sentence = split_sentences(previous.text)[-1]
        assert following.text.startswith(last_sentence)
    # Целый абзац попадает в текст ровно один раз: на его границе перекрытия нет.
    # Соседний абзац может попасть в тот же чанк — это слияние, а не повтор.
    joined = " ".join(chunk.text for chunk in chunks)
    assert joined.count("Короткий отдельный абзац.") == 1


def test_service_pages_and_lines_are_dropped() -> None:
    """Оглавление, титул и номера страниц в чанки не попадают."""
    title_page = _page(1, [_line("Клинические рекомендации")])
    toc_page = _page(
        2,
        [
            _line("Оглавление"),
            _line("1. Определение ...................... 3"),
            _line("2. Диагностика ...................... 4"),
            _line("3. Лечение .......................... 5"),
        ],
    )
    content_page = _page(
        3,
        [
            _line("1. Определение", top=700.0),
            _line("Текст определения по существу.", top=700.0 - LINE_GAP),
            _line("12", top=700.0 - 2 * LINE_GAP),
            _line("Продолжение текста определения.", top=700.0 - 3 * LINE_GAP),
        ],
    )

    chunks = build_chunks(
        [title_page, toc_page, content_page],
        GUIDELINE_ID,
        1,
        ChunkingParams(target_chars=1000, max_chars=1500),
    )

    text = " ".join(chunk.text for chunk in chunks)
    assert "Клинические рекомендации" not in text
    assert "......" not in text
    assert "Оглавление" not in text
    assert "Текст определения по существу." in text
    assert " Продолжение текста" in text


def test_chunk_spanning_pages_gets_one_rect_per_page() -> None:
    """Чанк через границу страницы получает по прямоугольнику на каждую страницу."""
    params = ChunkingParams(target_chars=200, min_chars=100, max_chars=300)
    first = _page(1, [_line("Начало длинного текста про диагностику.", top=200.0)])
    second = _page(2, [_line("Продолжение того же текста про диагностику.", top=700.0)])

    # Порог служебной страницы снижен: у синтетических страниц мало текста
    chunks = build_chunks([first, second], GUIDELINE_ID, 1, params, min_page_chars=1)
    spanning = [chunk for chunk in chunks if len(chunk.rects) == 2]

    assert spanning, "чанк через границу страницы не собрался"
    chunk = spanning[0]
    assert [rect.page for rect in chunk.rects] == [1, 2]
    assert chunk.page == 1
    assert chunk.bbox == chunk.rects[0].bbox


def test_chunk_ids_are_deterministic() -> None:
    """Два прогона чанкинга дают одинаковые идентификаторы, версия меняет их."""
    page = _sequential(
        "1. Определение", "Текст определения.", "2. Диагностика", "Текст диагностики."
    )
    params = ChunkingParams(target_chars=200, max_chars=400)

    first = build_chunks([page], GUIDELINE_ID, 1, params)
    second = build_chunks([page], GUIDELINE_ID, 1, params)
    other_version = build_chunks([page], GUIDELINE_ID, 2, params)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_id for chunk in first] != [chunk.chunk_id for chunk in other_version]


def test_chunk_id_depends_on_text_and_position() -> None:
    """Идентификатор зависит от текста и позиции, а не только от клинрека."""
    lines_a = [_line("Текст", top=700.0)]
    lines_b = [_line("Текст", top=600.0)]

    first = chunk_id_for(GUIDELINE_ID, 1, lines_a, "Текст")
    second = chunk_id_for(GUIDELINE_ID, 1, lines_b, "Текст")

    assert first != second


def test_sections_keep_heading_as_first_unit() -> None:
    """Заголовок остаётся первым куском секции: он попадает в текст чанка."""
    page = _sequential("2. Диагностика", "Измерение давления на обеих руках.")

    chunks = build_chunks([page], GUIDELINE_ID, 1, ChunkingParams(target_chars=1000))

    assert chunks[0].section == "2. Диагностика"
    assert chunks[0].text.startswith("2. Диагностика")
