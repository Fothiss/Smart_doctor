"""Проверки сервиса чата: отказы по запросу, ссылки, статус «не найдено»."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fakes import FakeEmbedder, FakeLLM, FakeSearchStore

from app.clients.vector_store import ScoredChunk
from app.config import ChatSettings
from app.schemas.chat import ChatAskRequest, ChatMessage, ChatStatus
from app.schemas.chunk import Chunk, ChunkRect
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.chat import (
    ChatGuidelineNotFoundError,
    ChatGuidelineNotReadyError,
    ChatRequestError,
    ChatService,
)
from app.services.guidelines import GuidelineService
from app.services.prompts.chat import LlmAnswer, LlmCitation
from app.services.prompts.rewrite import SearchQuery
from app.services.query_rewrite import QueryRewriter
from app.services.retrieval import RetrievalService

CHUNK_TEXT = "Целевой уровень АД — ниже 140/90 мм рт. ст. При хорошей переносимости — 130/80."
QUESTION = "до какого давления снижать пациенту 60 лет?"
THESIS = "целевой уровень артериального давления у пациента 60 лет"


def _ready_guideline(
    service: GuidelineService,
    *,
    status: GuidelineStatus = GuidelineStatus.READY,
    title: str = "Гипертензия",
) -> Guideline:
    """Записать манифест клинрека в хранилище теста."""
    guideline = Guideline(
        guideline_id=uuid4(),
        version=1,
        title=title,
        filename="kr.pdf",
        size_bytes=1024,
        sha256="0" * 64,
        status=status,
        created_at=datetime.now(UTC),
    )
    (service._dir / str(guideline.guideline_id)).mkdir(parents=True, exist_ok=True)
    service.save(guideline)
    return guideline


def _chunk(guideline_id: UUID, text: str = CHUNK_TEXT) -> Chunk:
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=guideline_id,
        guideline_version=1,
        section="3.2. Целевые уровни",
        text=text,
        chunk_index=0,
        page=9,
        bbox=(0.0, 0.0, 1.0, 1.0),
        rects=[ChunkRect(page=9, bbox=(0.0, 0.0, 1.0, 1.0))],
    )


def _thesis(expression: str = THESIS) -> SearchQuery:
    return SearchQuery(expression=expression, constraints=[], is_followup=False)


def _answer(*citations: LlmCitation, text: str = "Снижать до 140/90 [1].") -> LlmAnswer:
    return LlmAnswer(answer=text, citations=list(citations))


def _found(guideline_id: UUID, text: str = CHUNK_TEXT) -> ScoredChunk:
    return ScoredChunk(chunk=_chunk(guideline_id, text), score=0.8)


def _service(
    guidelines: GuidelineService, llm: FakeLLM, found: list[ScoredChunk], **settings: object
) -> ChatService:
    return ChatService(
        guidelines=guidelines,
        retrieval=RetrievalService(FakeEmbedder(), FakeSearchStore(found), top_k=8),
        rewriter=QueryRewriter(llm, window=4),
        llm=llm,
        settings=ChatSettings(**settings),
    )


def _request(guideline_ids: list[UUID], question: str = QUESTION) -> ChatAskRequest:
    return ChatAskRequest(guideline_ids=guideline_ids, question=question)


async def test_answer_with_confirmed_citation(service: GuidelineService) -> None:
    """Подтверждённая ссылка даёт статус answered и адрес фрагмента."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(_thesis(), _answer(LlmCitation(n=1, quote="ниже 140/90 мм рт. ст.")))

    result = await _service(service, llm, [_found(guideline.guideline_id)]).ask(
        _request([guideline.guideline_id])
    )

    assert result.status is ChatStatus.ANSWERED
    assert result.answer is not None and "[1]" in result.answer
    assert [citation.n for citation in result.citations] == [1]
    assert result.citations[0].guideline_id == guideline.guideline_id
    assert result.citations[0].page == 9
    assert result.search.expression == THESIS
    assert [item.title for item in result.searched_guidelines] == ["Гипертензия"]


async def test_empty_question_is_rejected(service: GuidelineService) -> None:
    guideline = _ready_guideline(service)
    llm = FakeLLM()

    with pytest.raises(ChatRequestError, match="question is required"):
        await _service(service, llm, []).ask(_request([guideline.guideline_id], "   "))

    assert llm.calls == []


async def test_too_long_question_is_rejected(service: GuidelineService) -> None:
    guideline = _ready_guideline(service)
    llm = FakeLLM()

    with pytest.raises(ChatRequestError, match="longer than"):
        await _service(service, llm, []).ask(_request([guideline.guideline_id], "в" * 2001))


async def test_no_guidelines_is_rejected(service: GuidelineService) -> None:
    with pytest.raises(ChatRequestError, match="at least one guideline"):
        await _service(service, FakeLLM(), []).ask(_request([]))


async def test_too_many_guidelines_are_rejected(service: GuidelineService) -> None:
    guideline = _ready_guideline(service)
    ids = [guideline.guideline_id] + [uuid4() for _ in range(5)]

    with pytest.raises(ChatRequestError, match="more than 5"):
        await _service(service, FakeLLM(), []).ask(_request(ids, "вопрос"))


async def test_unknown_guideline_is_rejected(service: GuidelineService) -> None:
    with pytest.raises(ChatGuidelineNotFoundError):
        await _service(service, FakeLLM(), []).ask(_request([uuid4()]))


async def test_not_ready_guideline_is_rejected(service: GuidelineService) -> None:
    guideline = _ready_guideline(service, status=GuidelineStatus.PROCESSING)

    with pytest.raises(ChatGuidelineNotReadyError, match="processing"):
        await _service(service, FakeLLM(), []).ask(_request([guideline.guideline_id]))


async def test_duplicate_guidelines_are_squashed(service: GuidelineService) -> None:
    """Дважды выбранный документ не превращается в два документа."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(_thesis(), _answer(LlmCitation(n=1, quote="ниже 140/90 мм рт. ст.")))

    result = await _service(service, llm, [_found(guideline.guideline_id)]).ask(
        _request([guideline.guideline_id, guideline.guideline_id])
    )

    assert len(result.searched_guidelines) == 1


async def test_empty_retrieval_does_not_call_answer_model(service: GuidelineService) -> None:
    """Без фрагментов модель ответа не вызывается: она не должна отвечать по памяти."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(_thesis())

    result = await _service(service, llm, []).ask(_request([guideline.guideline_id]))

    assert result.status is ChatStatus.NOT_FOUND
    assert result.answer is None
    assert len(llm.calls) == 1  # только переписывание запроса


async def test_answer_without_citations_is_not_found(service: GuidelineService) -> None:
    """Ответ без ссылок не показывается: это отказ по существу вопроса."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(_thesis(), _answer(text="Снижать до 140/90 [1]."))

    result = await _service(service, llm, [_found(guideline.guideline_id)]).ask(
        _request([guideline.guideline_id])
    )

    assert result.status is ChatStatus.NOT_FOUND
    assert result.citations == []
    assert result.search.expression == THESIS
    assert result.searched_guidelines[0].guideline_id == guideline.guideline_id


async def test_unconfirmed_quote_drops_citation(service: GuidelineService) -> None:
    """Цитата не из фрагмента — ссылка отбрасывается вместе с маркером."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(
        _thesis(),
        _answer(LlmCitation(n=1, quote="амлодипин 5 мг один раз в сутки"), text="Доза [1]."),
    )

    result = await _service(service, llm, [_found(guideline.guideline_id)]).ask(
        _request([guideline.guideline_id])
    )

    assert result.status is ChatStatus.NOT_FOUND


async def test_partial_citations_keep_answer_text_clean(service: GuidelineService) -> None:
    """Маркер без подтверждённой ссылки исчезает из текста ответа."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(
        _thesis(),
        LlmAnswer(
            answer="Снижать до 140/90 [1], контроль каждые 2 недели [2].",
            citations=[
                LlmCitation(n=1, quote="ниже 140/90 мм рт. ст."),
                LlmCitation(n=2, quote="каждые 2 недели у врача"),
            ],
        ),
    )

    result = await _service(service, llm, [_found(guideline.guideline_id)]).ask(
        _request([guideline.guideline_id])
    )

    assert result.status is ChatStatus.ANSWERED
    assert result.answer == "Снижать до 140/90 [1], контроль каждые 2 недели."


async def test_history_reaches_rewrite_prompt(service: GuidelineService) -> None:
    """Окно истории влияет на поисковый запрос, но не на текст ответа."""
    guideline = _ready_guideline(service)
    llm = FakeLLM(_thesis(), _answer(LlmCitation(n=1, quote="ниже 140/90 мм рт. ст.")))
    request = ChatAskRequest(
        guideline_ids=[guideline.guideline_id],
        question="а ночью?",
        history=[ChatMessage(role="user", text="до какого давления снижать?")],
    )

    await _service(service, llm, [_found(guideline.guideline_id)]).ask(request)

    assert "до какого давления снижать?" in llm.calls[0][1]
    assert "а ночью?" not in llm.calls[1][1].split("Вопрос врача:")[0]
