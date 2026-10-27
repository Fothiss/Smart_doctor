"""Проверка ссылок ответа на фрагменты клинрека.

Модель видит контекст под номерами и ссылается номерами. Код превращает номер в
фрагмент и проверяет, что приведённая цитата действительно есть в его тексте: без этого
ссылка была бы обещанием, а не адресом.
"""

import logging
import re
from collections.abc import Sequence

from app.schemas.chat import Citation
from app.schemas.chunk import Chunk
from app.services.prompts.chat import ContextFragment, LlmAnswer

logger = logging.getLogger(__name__)

MIN_QUOTE_CHARS = 10
"""Короче этого совпадение ничего не доказывает: три общих слова есть в любом тексте."""

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = dict.fromkeys(map(ord, "«»“”„‟\"'"), " ")
_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
"""Маркер ссылки: одиночный `[1]` или группа `[1, 3]` — модель пишет и так, и так."""


def normalize_for_match(text: str) -> str:
    """Привести текст к виду, пригодному для сверки цитаты.

    Клинрек свёрстан разными тире, кавычками и неразрывными пробелами, а модель
    воспроизводит фразу по памяти: требовать побайтового совпадения — значит отбрасывать
    верные ссылки.
    """
    lowered = text.lower().replace("ё", "е").translate(_DASHES).translate(_QUOTES)
    return " ".join(lowered.split())


def citation_supported(chunk_text: str, quote: str) -> bool:
    """Содержится ли цитата в тексте фрагмента дословно после нормализации."""
    normalized_quote = normalize_for_match(quote)
    if len(normalized_quote) < MIN_QUOTE_CHARS:
        return False
    return normalized_quote in normalize_for_match(chunk_text)


def resolve_citations(parsed: LlmAnswer, fragments: Sequence[ContextFragment]) -> list[Citation]:
    """Оставить только те ссылки, которые подтверждаются текстом фрагмента.

    Номер вне контекста, повтор номера и цитата не из фрагмента отбрасываются молча для
    пользователя и с записью в журнал: причина важна при разборе качества ответов.
    """
    by_number: dict[int, ContextFragment] = {fragment.n: fragment for fragment in fragments}
    resolved: list[Citation] = []
    seen: set[int] = set()

    for citation in parsed.citations:
        if citation.n in seen:
            continue
        fragment = by_number.get(citation.n)
        if fragment is None:
            logger.info("Dropped citation with unknown number %d", citation.n)
            continue
        if not citation_supported(fragment.chunk.text, citation.quote):
            logger.info("Dropped citation %d: quote is not in the fragment", citation.n)
            continue
        seen.add(citation.n)
        resolved.append(
            _to_citation(fragment.chunk, fragment.guideline_title, citation.n, citation.quote)
        )

    return resolved


def drop_unsupported_markers(answer: str, supported: set[int]) -> str:
    """Убрать из текста маркеры, за которыми не осталось подтверждённой ссылки.

    Иначе в ответе остаётся «[3]» без ссылки: врач видит номер, за которым ничего нет.
    Групповой маркер `[1, 3]` разбирается по номерам: неподтверждённые уходят из группы,
    а если не осталось ни одного — исчезает весь маркер.
    """
    cleaned = _MARKER.sub(
        lambda match: _clean_marker(match.group(0), match.group(1), supported), answer
    )
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    return " ".join(cleaned.split())


def _clean_marker(original: str, group: str, supported: set[int]) -> str:
    """Оставить в маркере только подтверждённые номера."""
    numbers = [int(part) for part in re.split(r"\s*,\s*", group)]
    kept = [number for number in numbers if number in supported]
    if not kept:
        return ""
    if len(kept) == len(numbers):
        return original
    return "[" + ", ".join(str(number) for number in kept) + "]"


def _to_citation(chunk: Chunk, guideline_title: str, n: int, quote: str) -> Citation:
    """Собрать ссылку ответа из фрагмента и цитаты модели."""
    return Citation(
        n=n,
        chunk_id=chunk.chunk_id,
        guideline_id=chunk.guideline_id,
        guideline_version=chunk.guideline_version,
        guideline_title=guideline_title,
        section=chunk.section,
        page=chunk.page,
        quote=quote.strip(),
    )
