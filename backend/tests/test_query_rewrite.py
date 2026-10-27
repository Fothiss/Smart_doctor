"""Проверки переписывания: тезис принят, условие потеряно, откат на склейку."""

from dataclasses import dataclass

import pytest
from fakes import FakeLLM

from app.clients.llm import LLMError
from app.services.prompts.rewrite import SearchQuery
from app.services.query_rewrite import QueryRewriter

LONG_QUESTION = "до какого давления снижать пациенту 60 лет с диабетом?"


@dataclass(frozen=True)
class Message:
    """Сообщение ленты для проверок."""

    role: str
    text: str


def _thesis(
    expression: str, constraints: list[str] | None = None, followup: bool = True
) -> SearchQuery:
    return SearchQuery(
        expression=expression, constraints=constraints or [], is_followup=followup
    )


async def test_valid_thesis_is_accepted() -> None:
    """Тезис с сохранёнными условиями идёт в поиск как есть."""
    llm = FakeLLM(
        _thesis("целевой уровень АД ниже 140/90 у пациента 60 лет с диабетом", ["60 лет", "диабет"])
    )

    result = await QueryRewriter(llm, window=4).rewrite(
        "а если ещё диабет?", [Message("user", "до какого давления снижать пациенту 60 лет?")]
    )

    assert result.rewritten is True
    assert result.constraints_lost == 0
    assert result.expression.startswith("целевой уровень АД")
    assert result.is_followup is True


async def test_lost_constraint_falls_back_to_concatenation() -> None:
    """Потерянное условие — откат: лучше склейка, чем ответ не про того пациента."""
    llm = FakeLLM(_thesis("целевой уровень АД в ночное время", ["60 лет", "диабет"]))

    result = await QueryRewriter(llm, window=4).rewrite(
        "а ночью?", [Message("user", LONG_QUESTION)]
    )

    assert result.rewritten is False
    assert result.constraints_lost == 2
    assert result.expression == f"{LONG_QUESTION} а ночью?"


async def test_empty_expression_falls_back() -> None:
    """Пустой тезис не уходит в поиск."""
    llm = FakeLLM(_thesis("   "))

    result = await QueryRewriter(llm, window=4).rewrite(
        "а ночью?", [Message("user", LONG_QUESTION)]
    )

    assert result.rewritten is False
    assert result.expression == f"{LONG_QUESTION} а ночью?"


async def test_short_expression_falls_back() -> None:
    """Обрывок вместо тезиса — тоже откат."""
    llm = FakeLLM(_thesis("давление"))

    result = await QueryRewriter(llm, window=4).rewrite(
        "а ночью?", [Message("user", LONG_QUESTION)]
    )

    assert result.rewritten is False


async def test_first_question_without_history_is_still_rewritten() -> None:
    """Первый вопрос тоже проходит переписывание: нормализуется форма запроса."""
    llm = FakeLLM(_thesis("целевой уровень артериального давления при гипертензии", followup=False))

    result = await QueryRewriter(llm, window=4).rewrite(
        "до какого давления снижать при гипертензии?", []
    )

    assert result.rewritten is True
    assert result.is_followup is False


async def test_fallback_without_history_uses_current_question() -> None:
    """Без истории откат склеивать не с чем: остаётся текущий вопрос."""
    llm = FakeLLM(_thesis(""))

    result = await QueryRewriter(llm, window=4).rewrite("а ночью?", [])

    assert result.expression == "а ночью?"
    assert result.is_followup is False


async def test_window_limits_history_in_prompt() -> None:
    """В промпт уходят только последние сообщения окна."""
    llm = FakeLLM(_thesis("целевой уровень АД у пациента 60 лет", ["60 лет"]))
    history = [Message("user", f"вопрос {index}") for index in range(10)]

    await QueryRewriter(llm, window=4).rewrite("а если диабет?", history)

    prompt = llm.calls[0][1]
    assert "вопрос 9" in prompt
    assert "вопрос 5" not in prompt


async def test_zero_window_sends_empty_history() -> None:
    """Нулевое окно — законная конфигурация: rewrite без истории."""
    llm = FakeLLM(_thesis("целевой уровень АД у пациента 60 лет"))

    await QueryRewriter(llm, window=0).rewrite("вопрос", [Message("user", "старое")])

    assert "старое" not in llm.calls[0][1]


async def test_rewrite_uses_rewrite_role() -> None:
    """Переписывание идёт ролью REWRITE: у неё своя модель."""
    llm = FakeLLM(_thesis("целевой уровень АД у пациента 60 лет"))

    await QueryRewriter(llm, window=4).rewrite("вопрос", [])

    assert llm.calls[0][3] == "rewrite"


async def test_provider_failure_is_not_swallowed() -> None:
    """Недоступная модель переписывания — отказ, а не тихая подмена поиска."""
    llm = FakeLLM(LLMError("GigaChat request failed"))

    with pytest.raises(LLMError):
        await QueryRewriter(llm, window=4).rewrite("вопрос", [])
