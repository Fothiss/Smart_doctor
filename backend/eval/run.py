"""Прогон эталонного набора чата: переписывание запроса (L1) и извлечение фрагментов (L2).

Один кейс — один вызов модели переписывания и один векторный поиск. Раннер не ходит в
сервис чата: системы-промпт в ``QueryRewriter`` не подменить, а менять прод-код ради
инструмента нельзя. Поэтому вызов модели повторён здесь, а приёмка тезиса (включая откат
на склейку с прошлым вопросом) берётся из ``app/services/query_rewrite.py`` как есть.

Итог прогона — число пройденных кейсов и отчёт в ``eval/reports/<name>.json``: по нему
сравниваются версии промпта. Запускать при остановленном бэкенде: локальный Qdrant
держит каталог заблокированным.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.embeddings import SentenceTransformerEmbedder
from app.clients.llm import LLMClient, ModelRole, build_llm_client
from app.clients.vector_store import ChunkVectorStore
from app.config import get_settings
from app.schemas.chat import ChatMessage
from app.services.citations import normalize_for_match
from app.services.prompts.rewrite import REWRITE_SYSTEM, SearchQuery, render_human
from app.services.query_rewrite import accept
from app.services.retrieval import fit_budget

EVAL_DIR = Path(__file__).resolve().parent
CASES_PATH = EVAL_DIR / "cases.toml"
VARIANTS_DIR = EVAL_DIR / "variants"
REPORTS_DIR = EVAL_DIR / "reports"
DUMP_PATH = EVAL_DIR / "chunk_dump.json"
BASELINE_PROMPT = "rewrite_a.md"
"""Файл текущего прод-промпта: он обязан совпадать с ``REWRITE_SYSTEM``."""

OUTSIDE_KIND = "outside"
"""Кейсы без ожидаемых фрагментов: считаются отдельно и в счёт пройденных не входят."""

RECALL_KS = (1, 3, 8, 16, 24)
"""Сетка k для recall@k и предел ранга: дальше позиция фрагмента уже не интересна."""

SEARCH_LIMIT = max(RECALL_KS)
"""Сколько фрагментов просим у хранилища: больше ``top_k``, чтобы знать ранг и за его пределами."""


@dataclass(frozen=True)
class Case:
    """Кейс набора: вопрос, окно истории и ожидания."""

    id: str
    question: str
    history: list[ChatMessage]
    expect_expression: list[str]
    expect_chunk_ids: list[str]
    kind: str = "answerable"
    keywords: list[str] = field(default_factory=list)

    @property
    def outside(self) -> bool:
        """Кейс про тему, которой в клинреке нет."""
        return self.kind == OUTSIDE_KIND


@dataclass
class CaseResult:
    """Результат одного кейса: обе проверки, выдача и длительности."""

    id: str
    kind: str
    l1: bool | None
    l2: bool | None
    passed: bool | None
    reason: str
    expression: str
    rewritten: bool
    constraints_lost: int
    hits_raw: list[str]
    hits_budget: list[str]
    expected: list[str]
    ranks: dict[str, int | None]
    mrr: float
    best_score: float
    rewrite_ms: int
    search_ms: int


def load_cases(path: Path) -> tuple[str, list[Case]]:
    """Прочитать набор и вернуть идентификатор клинрека вместе с кейсами."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    guideline_id = data.get("guideline_id")
    if not guideline_id:
        raise SystemExit(f"{path}: guideline_id is required")
    cases = [
        Case(
            id=raw.get("id", "?"),
            question=raw.get("question", ""),
            history=[
                ChatMessage(role=message["role"], text=message["text"])
                for message in raw.get("history", [])
            ],
            expect_expression=list(raw.get("expect_expression", [])),
            expect_chunk_ids=list(raw.get("expect_chunk_ids", [])),
            kind=raw.get("kind", "answerable"),
            keywords=list(raw.get("keywords", [])),
        )
        for raw in data.get("cases", [])
    ]
    return guideline_id, cases


def validate(cases: list[Case]) -> list[str]:
    """Проверить обязательные поля и форму кейсов."""
    problems: list[str] = []
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            problems.append(f"{case.id}: duplicate id")
        seen.add(case.id)
        if not case.question.strip():
            problems.append(f"{case.id}: question is required")
        if case.outside:
            if not case.keywords:
                problems.append(f"{case.id}: outside case needs keywords")
            if case.expect_chunk_ids:
                problems.append(f"{case.id}: outside case must not expect chunks")
        else:
            if not case.expect_expression:
                problems.append(f"{case.id}: expect_expression is required")
            if not case.expect_chunk_ids:
                problems.append(f"{case.id}: expect_chunk_ids is required")
    return problems


def alternatives(expectation: str) -> list[str]:
    """Разобрать ожидание на допустимые формулировки.

    Одно условие можно сохранить по-разному: «ХБП» и «хроническая болезнь почек» — это
    одно условие. Варианты разделены «|», достаточно любого. Иначе проверка мерила бы
    совпадение словоформы, а не сохранение условия.
    """
    return [part.strip() for part in expectation.split("|") if part.strip()]


def validate_against_dump(cases: list[Case], guideline_id: str) -> list[str]:
    """Сверить разметку с дампом чанков.

    Ожидаемое условие обязано быть в тексте ожидаемого фрагмента — иначе вопрос нечем
    зацепить в поиске. У уточнений условие обязано отсутствовать в самом вопросе —
    иначе кейс не проверяет переписывание. У тем вне документа ключевых слов не должно
    быть ни в одном фрагменте.
    """
    if not DUMP_PATH.exists():
        return [f"{DUMP_PATH} is missing: run dump_chunks.py first"]
    chunks = json.loads(DUMP_PATH.read_text(encoding="utf-8"))
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    blob = normalize_for_match(" ".join(chunk["text"] for chunk in chunks))

    problems: list[str] = []
    for case in cases:
        if case.outside:
            problems.extend(
                f"{case.id}: keyword {keyword!r} is present in the guideline"
                for keyword in case.keywords
                if normalize_for_match(keyword) in blob
            )
            continue
        texts = []
        for chunk_id in case.expect_chunk_ids:
            chunk = by_id.get(chunk_id)
            if chunk is None:
                problems.append(f"{case.id}: unknown chunk {chunk_id}")
                continue
            if chunk["guideline_id"] != guideline_id:
                problems.append(f"{case.id}: chunk {chunk_id} belongs to another guideline")
            texts.append(normalize_for_match(chunk["text"]))
        for expectation in case.expect_expression:
            forms = alternatives(expectation)
            if not any(normalize_for_match(form) in text for form in forms for text in texts):
                problems.append(f"{case.id}: {expectation!r} is not in the expected chunks")
            if case.history and all(
                normalize_for_match(form) in normalize_for_match(case.question) for form in forms
            ):
                problems.append(
                    f"{case.id}: {expectation!r} is in the question, so the case does not "
                    "check the history window"
                )
    return problems


def validate_input(cases: list[Case]) -> list[str]:
    """Проверить, что ожидаемые условия вообще есть во входе кейса.

    Переписывание не имеет права добавлять условия, которых не было в вопросе и
    истории, поэтому ожидание, отсутствующее во входе, невыполнимо в принципе: такой
    кейс мерил бы не качество модели, а ошибку разметки.
    """
    problems: list[str] = []
    for case in cases:
        if case.outside:
            continue
        source = normalize_for_match(
            " ".join([case.question, *(message.text for message in case.history)])
        )
        for expectation in case.expect_expression:
            forms = alternatives(expectation)
            if not any(normalize_for_match(form) in source for form in forms):
                problems.append(
                    f"{case.id}: {expectation!r} is not in the question or history"
                )
    return problems


def load_prompt(target: str | None) -> Path:
    """Найти файл системы-промпта: имя варианта или путь к файлу."""
    if target is None:
        return VARIANTS_DIR / BASELINE_PROMPT
    looks_like_path = target.endswith(".md") and ("/" in target or "\\" in target)
    if looks_like_path:
        path = Path(target)
        return path if path.is_absolute() else EVAL_DIR / path
    return VARIANTS_DIR / f"rewrite_{target}.md"


def check_baseline() -> None:
    """Убедиться, что файл базового варианта не разошёлся с прод-промптом.

    Без этой проверки baseline тихо измерял бы не тот промпт, что работает в чате, и
    сравнение версий было бы бессмысленным.
    """
    baseline = (VARIANTS_DIR / BASELINE_PROMPT).read_text(encoding="utf-8").strip()
    if baseline != REWRITE_SYSTEM.strip():
        raise SystemExit(
            f"{VARIANTS_DIR / BASELINE_PROMPT} does not match REWRITE_SYSTEM: "
            "sync it before running the eval"
        )


def _missing_phrases(expression: str, expected: list[str]) -> list[str]:
    """Условия кейса, которых не оказалось в поисковом запросе."""
    normalized = normalize_for_match(expression)
    return [
        expectation
        for expectation in expected
        if not any(normalize_for_match(form) in normalized for form in alternatives(expectation))
    ]


def _mean(values: list[float]) -> float:
    """Среднее по списку; пустой список даёт 0."""
    return round(sum(values) / len(values), 4) if values else 0.0


def ranks_of(expected: list[str], found: list[str]) -> dict[str, int | None]:
    """Позиция каждого ожидаемого фрагмента в выдаче; ``None`` — не найден.

    Ранг считается по полной выдаче (``SEARCH_LIMIT``), а не по бюджету: на бюджет
    влияют настройки контекста, и ранжирование должно быть от них независимо.
    """
    return {
        chunk_id: (found.index(chunk_id) + 1 if chunk_id in found else None)
        for chunk_id in expected
    }


def mrr_of(ranks: dict[str, int | None]) -> float:
    """Обратный ранг первого найденного ожидаемого фрагмента."""
    found = [rank for rank in ranks.values() if rank is not None]
    return round(1 / min(found), 4) if found else 0.0


def recall_of(ranks: dict[str, int | None], k: int) -> float:
    """Доля найденных ожидаемых фрагментов в первых ``k`` позициях."""
    if not ranks:
        return 0.0
    hits = sum(1 for rank in ranks.values() if rank is not None and rank <= k)
    return round(hits / len(ranks), 4)


async def run_case(
    case: Case,
    *,
    guideline_id: UUID,
    llm: LLMClient,
    embedder: SentenceTransformerEmbedder,
    store: ChunkVectorStore,
    prompt_text: str,
    top_k: int,
    max_context_chars: int,
) -> CaseResult:
    """Прогнать один кейс: переписывание, поиск, две проверки."""
    history: list[ChatMessage] = [] if case.outside else case.history

    started = time.perf_counter()
    parsed = await llm.structured(
        prompt_text,
        render_human(case.question, history),
        SearchQuery,
        role=ModelRole.REWRITE,
    )
    rewritten = accept(parsed, case.question, history)
    rewrite_ms = int((time.perf_counter() - started) * 1000)

    started = time.perf_counter()
    vector = await asyncio.to_thread(embedder.encode_query, rewritten.expression)
    found = await asyncio.to_thread(
        store.search, vector, [guideline_id], max(top_k, SEARCH_LIMIT)
    )
    kept = fit_budget(found, max_context_chars)
    search_ms = int((time.perf_counter() - started) * 1000)

    found_ids = [str(item.chunk.chunk_id) for item in found]
    hits_raw = found_ids[:top_k]
    hits_budget = [str(item.chunk.chunk_id) for item in kept]
    expected = list(case.expect_chunk_ids)
    ranks = ranks_of(expected, found_ids)
    mrr = mrr_of(ranks)
    best_score = round(found[0].score, 4) if found else 0.0

    if case.outside:
        return CaseResult(
            id=case.id,
            kind=case.kind,
            l1=None,
            l2=None,
            passed=None,
            reason="outside: not scored",
            expression=rewritten.expression,
            rewritten=rewritten.rewritten,
            constraints_lost=rewritten.constraints_lost,
            hits_raw=hits_raw,
            hits_budget=hits_budget,
            expected=expected,
            ranks=ranks,
            mrr=mrr,
            best_score=best_score,
            rewrite_ms=rewrite_ms,
            search_ms=search_ms,
        )

    missing = _missing_phrases(rewritten.expression, case.expect_expression)
    l1 = not missing
    expected_ids = set(case.expect_chunk_ids)
    l2 = bool(expected_ids & set(hits_budget))
    reasons = []
    if missing:
        reasons.append("expression lost: " + ", ".join(missing))
    if not l2:
        displaced = bool(expected_ids & set(hits_raw))
        reasons.append(
            "expected chunk displaced by context budget"
            if displaced
            else "expected chunk not found"
        )
    return CaseResult(
        id=case.id,
        kind=case.kind,
        l1=l1,
        l2=l2,
        passed=l1 and l2,
        reason="; ".join(reasons) or "ok",
        expression=rewritten.expression,
        rewritten=rewritten.rewritten,
        constraints_lost=rewritten.constraints_lost,
        hits_raw=hits_raw,
        hits_budget=hits_budget,
        expected=expected,
        ranks=ranks,
        mrr=mrr,
        best_score=best_score,
        rewrite_ms=rewrite_ms,
        search_ms=search_ms,
    )


def summarize(results: list[CaseResult]) -> dict[str, object]:
    """Собрать итоги прогона: счёт, метрики ранжирования и средние длительности."""
    scored = [item for item in results if item.passed is not None]
    rewrite = [item.rewrite_ms for item in scored]
    search = [item.search_ms for item in scored]
    count = len(scored)
    return {
        "cases": len(results),
        "scored": count,
        "passed": sum(1 for item in scored if item.passed),
        "l1": sum(1 for item in scored if item.l1),
        "l2": sum(1 for item in scored if item.l2),
        "outside": len(results) - count,
        "mrr": round(sum(item.mrr for item in scored) / count, 4) if count else 0.0,
        "recall": {
            f"@{k}": round(sum(recall_of(item.ranks, k) for item in scored) / count, 4)
            if count
            else 0.0
            for k in RECALL_KS
        },
        "rewrite_ms_avg": round(sum(rewrite) / count) if count else 0,
        "search_ms_avg": round(sum(search) / count) if count else 0,
    }


def print_report(name: str, results: list[CaseResult], totals: dict[str, object]) -> None:
    """Показать таблицу кейсов и итог прогона."""
    print(f"{'case':32} {'L1':>3} {'L2':>3} {'rank':>5} {'score':>6} {'rw':>6} {'se':>6}  reason")
    for item in results:
        l1 = "-" if item.l1 is None else ("ok" if item.l1 else "no")
        l2 = "-" if item.l2 is None else ("ok" if item.l2 else "no")
        rank = "-" if item.l1 is None else str(item.ranks.get(item.expected[0], "-"))
        print(
            f"{item.id:32} {l1:>3} {l2:>3} {rank:>5} {item.best_score:>6.3f} "
            f"{item.rewrite_ms:>6} {item.search_ms:>6}  {item.reason}"
        )
    recall = totals["recall"]
    recalls = ", ".join(f"{key} {value:.2f}" for key, value in recall.items())  # type: ignore[union-attr]
    print(
        f"\nVersion {name} -> {totals['passed']}/{totals['scored']} "
        f"(L1 {totals['l1']}/{totals['scored']}, L2 {totals['l2']}/{totals['scored']}), "
        f"{totals['outside']} outside, rewrite {totals['rewrite_ms_avg']} ms, "
        f"search {totals['search_ms_avg']} ms"
    )
    print(f"MRR {totals['mrr']:.3f}; recall {recalls}")


def compare(previous: dict[str, Any], results: list[CaseResult]) -> list[str]:
    """Показать, какие кейсы изменились относительно предыдущего отчёта."""
    before = {item["id"]: item for item in previous.get("cases") or []}
    changes = []
    for item in results:
        old = before.get(item.id)
        if old is None:
            changes.append(f"{item.id}: new case")
        elif old.get("passed") != item.passed:
            changes.append(f"{item.id}: {old.get('passed')} -> {item.passed}")
    return changes


async def replay(name: str, *, top_k: int, max_context_chars: int) -> None:
    """Пересчитать попадания по готовому отчёту, не вызывая модель.

    Вопросы переписывания в отчёте уже записаны, поэтому меняется только поиск: так
    подбирается ``top_k`` без вызовов LLM и без разброса между прогонами модели.
    """
    path = REPORTS_DIR / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"report {path} does not exist")
    report = json.loads(path.read_text(encoding="utf-8"))
    _, cases = load_cases(CASES_PATH)
    expected_by_id = {case.id: case.expect_chunk_ids for case in cases}
    settings = get_settings()
    embedder = SentenceTransformerEmbedder(settings.embedding)
    store = ChunkVectorStore.build(settings.database, settings.embedding.dimension)
    hits = total = 0
    mrrs: list[float] = []
    recalls: dict[int, list[float]] = {k: [] for k in RECALL_KS}
    try:
        await asyncio.to_thread(embedder.encode_query, "прогрев модели эмбеддингов")
        for case in report["cases"]:
            if case["l1"] is None:
                continue
            total += 1
            vector = await asyncio.to_thread(embedder.encode_query, case["expression"])
            found = await asyncio.to_thread(
                store.search,
                vector,
                [UUID(report["guideline_id"])],
                max(top_k, SEARCH_LIMIT),
            )
            found_ids = [str(item.chunk.chunk_id) for item in found]
            kept = {str(item.chunk.chunk_id) for item in fit_budget(found, max_context_chars)}
            expected = list(case.get("expected") or expected_by_id.get(case["id"], []))
            ranks = ranks_of(expected, found_ids)
            mrrs.append(mrr_of(ranks))
            for k in RECALL_KS:
                recalls[k].append(recall_of(ranks, k))
            if kept & set(expected):
                hits += 1
            else:
                print(f"  miss {case['id']}")
    finally:
        store.close()
    mean = _mean
    grid = ", ".join(f"@{k} {mean(recalls[k]):.2f}" for k in RECALL_KS)
    print(
        f"Replay {name} @ top_k={top_k}: hit {hits}/{total}, MRR {mean(mrrs):.3f}, recall {grid}"
    )


async def main() -> None:
    """Точка входа: проверка набора или полный прогон."""
    parser = argparse.ArgumentParser(description="Chat golden set eval")
    parser.add_argument("--name", default="run", help="имя отчёта: reports/<name>.json")
    parser.add_argument("--only", default="", help="идентификаторы кейсов через запятую")
    parser.add_argument("--prompt", default=None, help="вариант (b) или путь к файлу .md")
    parser.add_argument("--check", action="store_true", help="только проверить набор")
    parser.add_argument(
        "--no-history", action="store_true", help="игнорировать историю кейсов (для проверки L1)"
    )
    parser.add_argument(
        "--baseline", default=None, help="имя отчёта для сравнения: reports/<name>.json"
    )
    parser.add_argument(
        "--top-k", type=int, default=None, help="переопределить CHAT_TOP_K для прогона"
    )
    parser.add_argument(
        "--replay", default=None, help="пересчитать поиск по отчёту reports/<name>.json"
    )
    parser.add_argument(
        "--max-context",
        type=int,
        default=None,
        help="переопределить CHAT_MAX_CONTEXT_CHARS для прогона",
    )
    args = parser.parse_args()

    if args.replay:
        replay_settings = get_settings().chat
        await replay(
            args.replay,
            top_k=replay_settings.top_k if args.top_k is None else args.top_k,
            max_context_chars=(
                replay_settings.max_context_chars
                if args.max_context is None
                else args.max_context
            ),
        )
        return

    guideline_id, cases = load_cases(CASES_PATH)
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        cases = [case for case in cases if case.id in wanted]
        if not cases:
            raise SystemExit(f"no cases matched --only {args.only}")
    if args.no_history:
        cases = [
            Case(
                id=case.id,
                question=case.question,
                history=[],
                expect_expression=case.expect_expression,
                expect_chunk_ids=case.expect_chunk_ids,
                kind=case.kind,
                keywords=case.keywords,
            )
            for case in cases
        ]

    problems = validate(cases) + validate_input(cases) + validate_against_dump(cases, guideline_id)
    if problems:
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(f"{len(problems)} problem(s) in {CASES_PATH}")
    check_baseline()
    if args.check:
        print(f"{CASES_PATH}: {len(cases)} cases, no problems")
        return

    prompt_path = load_prompt(args.prompt)
    if not prompt_path.exists():
        raise SystemExit(f"prompt file {prompt_path} does not exist")
    prompt_text = prompt_path.read_text(encoding="utf-8")

    settings = get_settings()
    chat = settings.chat
    top_k = chat.top_k if args.top_k is None else args.top_k
    max_context_chars = (
        chat.max_context_chars if args.max_context is None else args.max_context
    )
    llm = build_llm_client(settings.llm)
    embedder = SentenceTransformerEmbedder(settings.embedding)
    store = ChunkVectorStore.build(settings.database, settings.embedding.dimension)
    try:
        # Прогрев: первый вызов эмбеддера поднимает веса и инициализирует устройство.
        # Без него длительность первого кейса — это загрузка модели, а не поиск.
        await asyncio.to_thread(embedder.encode_query, "прогрев модели эмбеддингов")
        results = [
            await run_case(
                case,
                guideline_id=UUID(guideline_id),
                llm=llm,
                embedder=embedder,
                store=store,
                prompt_text=prompt_text,
                top_k=top_k,
                max_context_chars=max_context_chars,
            )
            for case in cases
        ]
    finally:
        store.close()

    totals = summarize(results)
    print_report(args.name, results, totals)
    if args.baseline:
        baseline_path = REPORTS_DIR / f"{args.baseline}.json"
        if not baseline_path.exists():
            raise SystemExit(f"baseline report {baseline_path} does not exist")
        previous = json.loads(baseline_path.read_text(encoding="utf-8"))
        changes = compare(previous, results)
        print(f"\nChanges vs {args.baseline}: " + (", ".join(changes) if changes else "none"))

    REPORTS_DIR.mkdir(exist_ok=True)
    report = {
        "version": args.name,
        "created_at": datetime.now(UTC).isoformat(),
        "guideline_id": guideline_id,
        "prompt_file": prompt_path.name,
        "prompt_sha1": hashlib.sha1(prompt_text.encode("utf-8")).hexdigest(),
        "llm_model": llm.model_for(ModelRole.REWRITE),
        "embedding_model": settings.embedding.model_id,
        "top_k": top_k,
        "search_limit": max(top_k, SEARCH_LIMIT),
        "recall_ks": list(RECALL_KS),
        "max_context_chars": max_context_chars,
        "no_history": args.no_history,
        "totals": totals,
        "cases": [asdict(item) for item in results],
    }
    path = REPORTS_DIR / f"{args.name}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport: {path}")


if __name__ == "__main__":
    asyncio.run(main())
