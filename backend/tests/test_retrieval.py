"""Проверки поиска: фильтр по клинрекам, бюджет контекста, порог близости."""

from uuid import UUID, uuid4

from fakes import FakeEmbedder, FakeSearchStore

from app.clients.vector_store import ScoredChunk
from app.schemas.chunk import Chunk, ChunkRect
from app.services.retrieval import RetrievalService, fit_budget

GUIDELINE_ID = uuid4()
OTHER_GUIDELINE_ID = uuid4()


def _chunk(text: str, guideline_id: UUID = GUIDELINE_ID) -> Chunk:
    """Чанк с текстом заданной длины."""
    return Chunk(
        chunk_id=uuid4(),
        guideline_id=guideline_id,
        guideline_version=1,
        section="4. Лечение",
        text=text,
        chunk_index=0,
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        rects=[ChunkRect(page=1, bbox=(0.0, 0.0, 1.0, 1.0))],
    )


def _scored(text: str, score: float, guideline_id: UUID = GUIDELINE_ID) -> ScoredChunk:
    return ScoredChunk(chunk=_chunk(text, guideline_id), score=score)


def _service(store: FakeSearchStore, **kwargs: object) -> RetrievalService:
    defaults: dict[str, object] = {
        "top_k": 8,
        "max_context_chars": 12000,
        "min_score": 0.0,
    }
    defaults.update(kwargs)
    return RetrievalService(
        embedder=FakeEmbedder(),
        store=store,  # type: ignore[arg-type]
        **defaults,  # type: ignore[arg-type]
    )


async def test_no_guidelines_means_no_search() -> None:
    """Без выбранных документов поиск не выполняется вовсе."""
    store = FakeSearchStore([_scored("текст", 0.9)])

    assert await _service(store).search("вопрос", []) == []
    assert store.calls == []


async def test_query_is_encoded_once() -> None:
    """Запрос уходит в эмбеддер ровно один раз."""
    embedder = FakeEmbedder()
    service = RetrievalService(embedder=embedder, store=FakeSearchStore(), top_k=5)

    await service.search("до какого давления снижать", [GUIDELINE_ID])

    assert embedder.query_calls == ["до какого давления снижать"]


async def test_selected_guidelines_are_passed_to_store() -> None:
    """Фильтр по документам доходит до хранилища целиком."""
    store = FakeSearchStore()
    service = _service(store, top_k=3)

    await service.search("вопрос", [GUIDELINE_ID, OTHER_GUIDELINE_ID])

    assert store.calls == [([GUIDELINE_ID, OTHER_GUIDELINE_ID], 3)]


async def test_single_guideline_is_not_a_special_case() -> None:
    """Один документ — такой же запрос, а не отдельная ветка."""
    store = FakeSearchStore([_scored("текст", 0.5)])

    found = await _service(store).search("вопрос", [GUIDELINE_ID])

    assert [item.chunk.text for item in found] == ["текст"]


async def test_empty_result_stays_empty() -> None:
    """Пустой результат поиска — пустой список, а не ошибка."""
    assert await _service(FakeSearchStore()).search("вопрос", [GUIDELINE_ID]) == []


async def test_context_budget_drops_weakest() -> None:
    """В бюджет контекста попадают сильнейшие фрагменты."""
    store = FakeSearchStore(
        [_scored("а" * 5000, 0.9), _scored("б" * 5000, 0.8), _scored("в" * 5000, 0.7)]
    )

    found = await _service(store, max_context_chars=11000).search("вопрос", [GUIDELINE_ID])

    assert len(found) == 2
    assert [item.score for item in found] == [0.9, 0.8]


async def test_oversized_single_fragment_is_kept() -> None:
    """Один слишком длинный фрагмент остаётся: иначе ответа не будет вовсе."""
    store = FakeSearchStore([_scored("а" * 20000, 0.9)])

    found = await _service(store, max_context_chars=1000).search("вопрос", [GUIDELINE_ID])

    assert len(found) == 1


async def test_min_score_filters_weak_fragments() -> None:
    """Порог близости отсекает слабые фрагменты, когда он включён."""
    store = FakeSearchStore([_scored("сильный", 0.8), _scored("слабый", 0.2)])

    found = await _service(store, min_score=0.5).search("вопрос", [GUIDELINE_ID])

    assert [item.chunk.text for item in found] == ["сильный"]


def test_fit_budget_keeps_order() -> None:
    """Укладка в бюджет не меняет порядок фрагментов."""
    items = [_scored("а" * 100, 0.9), _scored("б" * 100, 0.8)]

    assert fit_budget(items, 500) == items
