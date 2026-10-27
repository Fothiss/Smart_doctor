"""Чат по выбранным клинрекам.

Один вопрос — один проход: проверка документов, переписывание запроса, поиск фрагментов
только по выбранным клинрекам, один вызов модели и сверка её ссылок. Лента диалога не
хранится и на ответ не влияет: она нужна лишь переписыванию запроса, чтобы короткое
уточнение не потеряло предмет разговора.
"""

import logging
from collections.abc import Sequence
from uuid import UUID

from app.clients.llm import LLMClient, ModelRole
from app.config.chat import ChatSettings
from app.schemas.chat import (
    ChatAnswer,
    ChatAskRequest,
    ChatGuidelineRef,
    ChatMessage,
    ChatStatus,
    SearchInfo,
)
from app.schemas.guideline import Guideline, GuidelineStatus
from app.services.citations import drop_unsupported_markers, resolve_citations
from app.services.guidelines import GuidelineNotFoundError, GuidelineService
from app.services.prompts.chat import (
    CHAT_SYSTEM,
    ContextFragment,
    LlmAnswer,
    render_human,
)
from app.services.query_rewrite import QueryRewriter
from app.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)

QUESTION_MAX_CHARS = 2000
"""Предел вопроса: длиннее — это уже не вопрос, а протокол, и его место в форме."""


class ChatError(Exception):
    """Базовая ошибка чата."""


class ChatRequestError(ChatError):
    """Запрос непригоден: пустой вопрос, нет документов, слишком много документов."""


class ChatGuidelineNotFoundError(ChatError):
    """Выбранного клинрека нет в библиотеке."""

    def __init__(self, guideline_id: UUID) -> None:
        super().__init__(f"guideline {guideline_id} not found")
        self.guideline_id = guideline_id


class ChatGuidelineNotReadyError(ChatError):
    """Клинрек ещё не готов: его фрагментов не существует."""

    def __init__(self, guideline: Guideline) -> None:
        super().__init__(
            f"guideline {guideline.guideline_id} is {guideline.status.value}, "
            "only ready guidelines can answer questions"
        )
        self.guideline = guideline


class ChatService:
    """Вопрос врача к выбранным клинрекам."""

    def __init__(
        self,
        guidelines: GuidelineService,
        retrieval: RetrievalService,
        rewriter: QueryRewriter,
        llm: LLMClient,
        settings: ChatSettings,
    ) -> None:
        self._guidelines = guidelines
        self._retrieval = retrieval
        self._rewriter = rewriter
        self._llm = llm
        self._settings = settings

    async def ask(self, request: ChatAskRequest) -> ChatAnswer:
        """Ответить на вопрос по выбранным клинрекам.

        Порядок проверок: сначала документы, затем переписывание. Переписывание стоит
        вызова модели, а неизвестный клинрек должен отказывать до траты токенов.
        """
        question = _require_question(request.question)
        guidelines = self._resolve_guidelines(request.guideline_ids)

        rewritten = await self._rewriter.rewrite(question, _history(request.history))
        titles = {guideline.guideline_id: guideline.title for guideline in guidelines}
        found = await self._retrieval.search(
            rewritten.expression, [guideline.guideline_id for guideline in guidelines]
        )
        fragments = [
            ContextFragment(
                n=index + 1,
                chunk=item.chunk,
                guideline_title=titles[item.chunk.guideline_id],
            )
            for index, item in enumerate(found)
        ]
        search_info = SearchInfo(
            expression=rewritten.expression,
            rewritten=rewritten.rewritten,
            constraints_lost=rewritten.constraints_lost,
        )
        searched = _searched_guidelines(guidelines)

        logger.info(
            "Chat question: guidelines=%d fragments=%d rewritten=%s",
            len(guidelines),
            len(fragments),
            rewritten.rewritten,
        )

        if not fragments:
            return _not_found(search_info, searched)

        parsed: LlmAnswer = await self._llm.structured(
            CHAT_SYSTEM, render_human(question, fragments), LlmAnswer, role=ModelRole.ANSWER
        )
        citations = resolve_citations(parsed, fragments)
        if not citations:
            logger.info("Chat answer rejected: no confirmed citations")
            return _not_found(search_info, searched)

        answer = drop_unsupported_markers(parsed.answer, {citation.n for citation in citations})
        if answer == "":
            logger.info("Chat answer rejected: empty text after marker cleanup")
            return _not_found(search_info, searched)

        return ChatAnswer(
            status=ChatStatus.ANSWERED,
            answer=answer,
            citations=citations,
            search=search_info,
            searched_guidelines=searched,
        )

    def _resolve_guidelines(self, raw_ids: Sequence[UUID]) -> list[Guideline]:
        """Проверить выбранные документы и вернуть их метаданные.

        Дубли в запросе снимаются: дважды выбранный клинрек не должен расширять выдачу.
        """
        ids = list(dict.fromkeys(raw_ids))
        if not ids:
            raise ChatRequestError("at least one guideline is required")
        if len(ids) > self._settings.max_guidelines:
            raise ChatRequestError(
                f"more than {self._settings.max_guidelines} guidelines are not supported"
            )

        resolved: list[Guideline] = []
        for guideline_id in ids:
            try:
                guideline = self._guidelines.get(guideline_id)
            except GuidelineNotFoundError as exc:
                raise ChatGuidelineNotFoundError(guideline_id) from exc
            if guideline.status is not GuidelineStatus.READY:
                raise ChatGuidelineNotReadyError(guideline)
            resolved.append(guideline)
        return resolved


def _require_question(raw: str) -> str:
    """Потребовать непустой вопрос в пределах длины."""
    question = (raw or "").strip()
    if not question:
        raise ChatRequestError("question is required")
    if len(question) > QUESTION_MAX_CHARS:
        raise ChatRequestError(f"question is longer than {QUESTION_MAX_CHARS} characters")
    return question


def _history(messages: Sequence[ChatMessage]) -> list[ChatMessage]:
    """Лента как есть: окно отсекает переписывание, ему виднее."""
    return list(messages)


def _searched_guidelines(guidelines: Sequence[Guideline]) -> list[ChatGuidelineRef]:
    """Документы, по которым выполнялся поиск."""
    return [
        ChatGuidelineRef(
            guideline_id=guideline.guideline_id, title=guideline.title, version=guideline.version
        )
        for guideline in guidelines
    ]


def _not_found(
    search: SearchInfo, searched: Sequence[ChatGuidelineRef]
) -> ChatAnswer:
    """Отказ по существу вопроса: ответа в документах нет."""
    return ChatAnswer(
        status=ChatStatus.NOT_FOUND,
        answer=None,
        citations=[],
        search=search,
        searched_guidelines=list(searched),
    )
