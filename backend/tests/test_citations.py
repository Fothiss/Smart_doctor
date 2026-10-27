"""Проверки сверки цитат: нормализация, подтверждение, чистка маркеров."""

from uuid import uuid4

from app.schemas.chunk import Chunk, ChunkRect
from app.services.citations import (
    MIN_QUOTE_CHARS,
    citation_supported,
    drop_unsupported_markers,
    normalize_for_match,
    resolve_citations,
)
from app.services.prompts.chat import ContextFragment, LlmAnswer, LlmCitation

CHUNK_TEXT = "Целевой уровень АД — ниже 140/90 мм рт. ст. При хорошей переносимости — 130/80."


def _fragment(n: int = 1, text: str = CHUNK_TEXT, title: str = "Гипертензия") -> ContextFragment:
    chunk = Chunk(
        chunk_id=uuid4(),
        guideline_id=uuid4(),
        guideline_version=3,
        section="3.2. Целевые уровни",
        text=text,
        chunk_index=0,
        page=9,
        bbox=(0.0, 0.0, 1.0, 1.0),
        rects=[ChunkRect(page=9, bbox=(0.0, 0.0, 1.0, 1.0))],
    )
    return ContextFragment(n=n, chunk=chunk, guideline_title=title)


def _answer(*citations: LlmCitation) -> LlmAnswer:
    return LlmAnswer(answer="ответ", citations=list(citations))


def test_normalize_unifies_case_yo_and_dashes() -> None:
    """Регистр, ё, тире, кавычки и пробелы не должны мешать сверке."""
    assert normalize_for_match("  Целевой  УРОВЕНЬ — 130/80 «ёлка» ") == normalize_for_match(
        "целевой уровень - 130/80 елка"
    )


def test_exact_quote_is_supported() -> None:
    assert citation_supported(CHUNK_TEXT, "ниже 140/90 мм рт. ст.")


def test_quote_with_different_dashes_is_supported() -> None:
    """Модель воспроизводит фразу по памяти: другое тире — не повод терять ссылку."""
    assert citation_supported(CHUNK_TEXT, "Целевой уровень АД - ниже 140/90 мм рт. ст.")


def test_quote_from_other_text_is_not_supported() -> None:
    assert not citation_supported(CHUNK_TEXT, "амлодипин 5 мг один раз в сутки")


def test_short_quote_is_not_supported() -> None:
    """Совпадение из нескольких слов ничего не доказывает."""
    assert len("140/90") < MIN_QUOTE_CHARS
    assert not citation_supported(CHUNK_TEXT, "140/90")


def test_resolve_keeps_supported_citation_with_address() -> None:
    """Подтверждённая ссылка несёт всё, что нужно для перехода в оригинал."""
    fragment = _fragment()

    resolved = resolve_citations(
        _answer(LlmCitation(n=1, quote="ниже 140/90 мм рт. ст.")), [fragment]
    )

    assert len(resolved) == 1
    citation = resolved[0]
    assert (citation.n, citation.page, citation.section) == (1, 9, "3.2. Целевые уровни")
    assert citation.guideline_version == 3
    assert citation.guideline_title == "Гипертензия"
    assert citation.chunk_id == fragment.chunk.chunk_id


def test_resolve_drops_unknown_number() -> None:
    """Ссылка на номер вне контекста не может попасть в ответ."""
    parsed = _answer(LlmCitation(n=7, quote="ниже 140/90 мм рт. ст."))

    assert resolve_citations(parsed, [_fragment()]) == []


def test_resolve_drops_quote_not_in_fragment() -> None:
    assert (
        resolve_citations(_answer(LlmCitation(n=1, quote="амлодипин 5 мг в сутки")), [_fragment()])
        == []
    )


def test_resolve_deduplicates_numbers() -> None:
    """Повторная ссылка на тот же фрагмент не должна дублироваться в ответе."""
    resolved = resolve_citations(
        _answer(
            LlmCitation(n=1, quote="ниже 140/90 мм рт. ст."),
            LlmCitation(n=1, quote="При хорошей переносимости"),
        ),
        [_fragment()],
    )

    assert len(resolved) == 1


def test_resolve_keeps_only_supported_of_several() -> None:
    fragments = [_fragment(), _fragment(n=2, text="Амлодипин 5 мг один раз в сутки.")]

    resolved = resolve_citations(
        _answer(
            LlmCitation(n=1, quote="ниже 140/90 мм рт. ст."),
            LlmCitation(n=2, quote="ниже 140/90 мм рт. ст."),
        ),
        fragments,
    )

    assert [citation.n for citation in resolved] == [1]


def test_markers_without_citation_are_removed() -> None:
    """Маркер без подтверждённой ссылки — это номер, за которым ничего нет."""
    cleaned = drop_unsupported_markers("Снижать до 140/90 [1], контроль [2].", {1})

    assert cleaned == "Снижать до 140/90 [1], контроль."


def test_marker_cleanup_keeps_text_of_supported() -> None:
    assert drop_unsupported_markers("Ответ [1] и [3].", {1, 3}) == "Ответ [1] и [3]."


def test_group_marker_loses_unsupported_number() -> None:
    """Из группы «[1, 3]» неподтверждённый номер уходит, подтверждённый остаётся."""
    cleaned = drop_unsupported_markers("Схемы [1, 3] рекомендованы.", {1})

    assert cleaned == "Схемы [1] рекомендованы."


def test_group_marker_disappears_when_nothing_left() -> None:
    assert drop_unsupported_markers("Схемы [2, 3] рекомендованы.", {1}) == "Схемы рекомендованы."
