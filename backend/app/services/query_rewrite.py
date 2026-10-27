"""Переписывание вопроса врача в поисковый тезис.

Вызывается на каждый вопрос: короткая реплика вроде «а если ещё диабет?» без этого не
ищется вовсе. Результат модели не принимается на веру — проверяется на потерю условий
и при провале заменяется детерминированной склейкой с предыдущим вопросом.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.clients.llm import LLMClient, ModelRole
from app.services.prompts.rewrite import (
    REWRITE_SYSTEM,
    DialogueMessage,
    SearchQuery,
    render_human,
)

logger = logging.getLogger(__name__)

MIN_EXPRESSION_CHARS = 15
"""Короче этого — не тезис, а обрывок: в поиск такое отправлять нельзя."""

MAX_EXPRESSION_CHARS = 400
"""Длиннее этого эмбеддер уже не помогает: лишние слова размывают вектор."""


@dataclass(frozen=True)
class RewrittenQuery:
    """Поисковый тезис вместе с признаками того, откуда он взялся."""

    expression: str
    rewritten: bool
    """False — модель не справилась, использована склейка с прошлым вопросом."""

    constraints_lost: int
    """Сколько условий вопроса не попало в тезис модели; на откате больше нуля."""

    is_followup: bool


def normalize(text: str) -> str:
    """Привести текст к виду, пригодному для сравнения: регистр, ё, пробелы."""
    lowered = text.lower().replace("ё", "е")
    return " ".join(lowered.split())


class QueryRewriter:
    """Превращает вопрос и окно истории в тезис для векторного поиска."""

    def __init__(self, llm: LLMClient, window: int) -> None:
        self._llm = llm
        self._window = window

    async def rewrite(
        self, question: str, history: Sequence[DialogueMessage]
    ) -> RewrittenQuery:
        """Сформировать поисковый тезис под текущий вопрос.

        Ошибку модели здесь не глотаем: недоступный LLM — это отказ, который вызывающий
        превращает в `502`, а не молчаливая подмена поиска.
        """
        window = list(history)[-self._window :] if self._window > 0 else []
        parsed = await self._llm.structured(
            REWRITE_SYSTEM,
            render_human(question, window),
            SearchQuery,
            role=ModelRole.REWRITE,
        )
        return accept(parsed, question, window)


def accept(
    parsed: SearchQuery, question: str, window: Sequence[DialogueMessage]
) -> RewrittenQuery:
    """Принять тезис модели или откатиться на склейку.

    Отказы: пустой и слишком короткий тезис, потерянное условие. Тезис, который длиннее
    предела, обрезается по словам, а не отбрасывается: это не порча, а лишний шум.
    """
    expression = " ".join(parsed.expression.split())
    if len(expression) < MIN_EXPRESSION_CHARS:
        logger.info("Rewrite returned a too short expression")
        return _fallback(question, window, constraints_lost=0, is_followup=parsed.is_followup)

    lost = [item for item in parsed.constraints if not _contains(expression, item)]
    if lost:
        logger.info("Rewrite dropped %d constraints", len(lost))
        return _fallback(
            question, window, constraints_lost=len(lost), is_followup=parsed.is_followup
        )

    return RewrittenQuery(
        expression=expression[:MAX_EXPRESSION_CHARS],
        rewritten=True,
        constraints_lost=0,
        is_followup=parsed.is_followup,
    )


def _contains(expression: str, constraint: str) -> bool:
    """Входит ли условие в тезис с точностью до регистра и пробелов."""
    needle = normalize(constraint)
    return needle == "" or needle in normalize(expression)


def _fallback(
    question: str,
    window: Sequence[DialogueMessage],
    *,
    constraints_lost: int,
    is_followup: bool,
) -> RewrittenQuery:
    """Детерминированная склейка: предмет разговора сохраняется без модели."""
    previous = next(
        (message.text for message in reversed(list(window)) if message.role == "user"), None
    )
    expression = question if previous is None else f"{previous} {question}"
    return RewrittenQuery(
        expression=expression[:MAX_EXPRESSION_CHARS],
        rewritten=False,
        constraints_lost=constraints_lost,
        is_followup=is_followup if previous is not None else False,
    )
