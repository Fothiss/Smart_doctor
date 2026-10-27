# Design

## Context

См. `proposal.md` — Why. Существенное из кода:

- Пайплайн чата: `QueryRewriter.rewrite` → `RetrievalService.search` → LLM-ответ → `resolve_citations`.
  Раннеру нужны только первые два шага.
- `QueryRewriter` жёстко берёт `REWRITE_SYSTEM` из модуля `app/services/prompts/rewrite.py`;
  параметра для подмены промпта нет.
- `accept(parsed, question, window)` — чистая функция: принимает разобранный `SearchQuery` и
  откатывается на склейку. Переиспользуема как есть.
- `RetrievalService.search` уже применяет `fit_budget` внутри, поэтому «до бюджета» и «после бюджета»
  — это два разных замера, а не один.
- `ChunkVectorStore` умеет только `search`/`get`/`upsert`/`delete_guideline`; перечисления чанков нет.
- Параметры: `top_k=8`, `max_context_chars=12000`, `min_score=0`, `history_window=4`. Готовый
  клинрек: `7434ecc7-58ec-4925-9b93-cb4d507646ca` («Гипертензия», КР 62/3, 427 чанков).

## Goals / Non-Goals

**Goals:**

- Baseline и сравнение по одному изменяемому компоненту (промпт переписывания), без правок прод-кода.
- Воспроизводимый след: набор, дамп чанков и отчёты лежат в репозитории.
- Замер времени на этап, чтобы видеть цену правки.

**Non-Goals:**

- Оценка качества ответа (`answered`/`not_found`, ссылки, выдумки) — это L3/L4, следующий набор.
- Автоматический прогон в CI: нужны реальные веса, GigaChat и локальный Qdrant.
- Порог `min_score` и подбор `top_k`: набор даёт материал, решение вне этого change.

## Decisions

**Раннер не использует `QueryRewriter`, а повторяет его вызов.**
`llm.structured(prompt_text, render_human(question, window), SearchQuery, role=REWRITE)` +
`accept(...)`. Альтернативы: (а) добавить в `QueryRewriter` параметр системы-промпта — это правка
прод-кода ради инструмента; (б) подменить константу через `monkeypatch` — скрытая мутация модуля,
расходятся с реальным вызовом незаметно. Дублируется только сам вызов модели, логика приёмки — из
прод-кода.

**Защита от расхождения baseline с прод-промптом.** Перед прогоном `run.py` сравнивает содержимое
`variants/rewrite_a.md` с `REWRITE_SYSTEM` байт-в-байт и падает при отличии. Иначе «baseline» тихо
меряет не то, что работает в чате.

**Кейсы в TOML, а не YAML.** `tomllib` есть в стандартной библиотеке, `pyyaml` в зависимостях нет.
Формат — массив таблиц `[[cases]]`, чтение только на вход. Альтернатива — JSON: хуже читается в диффе
из-за экранирования кириллицы и длинных строк; альтернатива — добавить `pyyaml` в dev-группу ради
одного файла.

**Два замера выдачи.** Раннер зовёт `embedder.encode_query` + `store.search` напрямую, затем
`fit_budget` из `app/services/retrieval.py`: `hits_raw` (top_k) и `hits_budget` (после бюджета).
Попадание считается по `hits_budget`; `hits_raw` нужен, чтобы отличить «поиск не нашёл» от «бюджет
вытеснил».

**Кейсы «вне документа» отделены полем `kind = "outside"`** и без `expect_chunk_ids`. В счёт
`passed` не входят, в отчёт пишется близость лучшего фрагмента.

**Дампер — одноразовый скрипт, не сервис.** Идёт мимо `ChunkVectorStore` (в нём нет перечисления):
`QdrantClient.scroll` по коллекции `f"{qdrant_collection}__{dimension}"`. Результат —
`chunk_dump.json` + читаемая выжимка `chunk_dump.md` с `chunk_id, section, page, text`. Коммитим:
по нему размечаются `expect_chunk_ids`.

**Раскладка:**

```
backend/eval/
  cases.toml
  run.py              # прогон: rewrite -> search -> проверки -> reports/<name>.json + stdout
  dump_chunks.py      # одноразовый дамп чанков из локального Qdrant
  variants/rewrite_a.md
  variants/rewrite_b.md   # слот для правки промпта
  chunk_dump.json     # выход дампера, вход разметки
  reports/a.json
  reports/b.json
EVAL.md
```

Запуск: `cd backend; .\.venv\Scripts\python.exe eval\run.py --name a` — скрипт сам добавляет корень
`backend` в `sys.path`, как это делает `app/__main__.py`.

**Отчёт.** JSON: `version`, `prompt_file`, `prompt_sha1`, `created_at`, `totals{passed, cases, l1,
l2, outside}`, `timing{rewrite_ms_avg, search_ms_avg, total_ms}`, `cases[{id, kind, l1, l2, passed,
expression, constraints_lost, rewritten, hits_raw, hits_budget, best_score, reason}]`. В stdout —
таблица и итог вида `Version A -> 11/20 (L1 16/20, L2 13/16)`.

## Risks / Trade-offs

- **Недетерминизм GigaChat при `temperature=0`** → считать разницу в 1 кейс шумом; писать это в
  `EVAL.md`; прогонять обе версии на одном и том же наборе в одном окне.
- **`chunk_id` меняются при смене параметров чанкинга** (`uuid5` от `guideline_id|version|position|
  sha1(text)`) → `chunk_dump.json` в репозитории хранит и текст чанка, поэтому переразметку можно
  сделать по цитате, а не заново глазами.
- **Лексическое совпадение вопроса и чанка** делает кейс тривиальным → при разметке вопрос
  формулируется после выбора чанка и не повторяет его текст; в `EVAL.md` фиксируем это правило.
- **Локальный Qdrant держит блокировку каталога** → прогон запускать при остановленном бэкенде; либо
  `QDRANT_MODE=server`. Симптом — ошибка открытия хранилища, не тихий сбой.
- **20 кейсов на одном документе** → разрешение ~5% и никаких выводов о других клинреках; в `EVAL.md`
  это заявлено ограничением.
- **Прод-код выглядит затронутым** → нет: единственная зависимость рантайма от прода — импорт
  `accept`, `REWRITE_SYSTEM`, `RetrievalService`, `fit_budget`, `build_llm_client`.

## Open Questions

- Какая именно правка `rewrite_b.md` — за пользователем, слот готов.
- Нужен ли второй набор по L3/L4 — вне этого change.
