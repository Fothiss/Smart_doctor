"""Проверки извлечения текста и геометрии страниц."""

from pathlib import Path

import pytest

from app.services.pdf_text import (
    MIN_PAGE_CHARS,
    MissingTextLayerError,
    PdfTextError,
    ensure_text_layer,
    read_pages,
)


def test_pages_are_read_in_order(mini_pdf: Path) -> None:
    """Страницы выдаются по порядку и с текстом."""
    pages = read_pages(mini_pdf)

    assert [page.number for page in pages] == [1, 2, 3, 4]
    assert [page.chars for page in pages] == [40, 111, 482, 94]


def test_lines_are_inside_page_bounds(mini_pdf: Path) -> None:
    """Прямоугольник каждой строки попадает в границы страницы."""
    for page in read_pages(mini_pdf):
        assert page.lines, f"страница {page.number} без строк"
        for line in page.lines:
            assert 0 <= line.x0 < line.x1 <= page.width
            assert 0 <= line.bottom < line.top <= page.height
            assert line.size > 0
            assert line.font


def test_plain_page_coordinates_are_flipped_to_pdf_space(mini_pdf: Path) -> None:
    """Текст с верхнего края страницы получает большую координату Y."""
    page = read_pages(mini_pdf)[2]
    title = page.lines[0]

    assert title.text == "1. Definition"
    # В фикстуре строка поставлена на 770 pt от нижнего края страницы высотой 842
    assert 760 < title.bottom < 780
    assert title.x0 == pytest.approx(72.0)


def test_rotated_page_is_converted_to_unrotated_space(mini_pdf: Path) -> None:
    """Координаты повёрнутой страницы приводятся к неразвёрнутой странице.

    Эталон — сам PDF: текст поставлен в потоке страницы на ``(72, 770)``, поэтому
    после преобразования он обязан оказаться там же, иначе подсветка уедет.
    """
    page = read_pages(mini_pdf)[3]

    assert page.rotation == 90
    assert (page.width, page.height) == (595.0, 842.0)
    boxes = {line.text: line for line in page.lines if line.text in {"2.", "Diagnostics"}}
    assert set(boxes) == {"2.", "Diagnostics"}
    for line in boxes.values():
        assert 0 <= line.x0 < line.x1 <= page.width
        assert 0 <= line.bottom < line.top <= page.height
    assert boxes["2."].x0 == pytest.approx(72.0, abs=0.5)
    assert boxes["Diagnostics"].x1 == pytest.approx(147.4, abs=1.0)
    assert boxes["Diagnostics"].top == pytest.approx(779.5, abs=0.5)


def test_scan_without_text_layer_is_rejected(scanned_pdf: Path) -> None:
    """PDF без текстового слоя даёт понятную причину, а не пустой набор чанков."""
    pages = read_pages(scanned_pdf)

    assert [page.chars for page in pages] == [0, 0]
    with pytest.raises(MissingTextLayerError, match="no text layer"):
        ensure_text_layer(pages)


def test_page_slightly_above_threshold_is_accepted(mini_pdf: Path) -> None:
    """Документ с текстом проходит проверку текстового слоя."""
    pages = read_pages(mini_pdf)

    ensure_text_layer(pages)
    assert pages[2].chars > MIN_PAGE_CHARS


def test_broken_file_reports_pdf_error(tmp_path: Path) -> None:
    """Битый файл не молчит, а падает понятной ошибкой."""
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nnot a real document")

    with pytest.raises(PdfTextError):
        read_pages(broken)
