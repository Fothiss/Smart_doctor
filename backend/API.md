# API — минимальный набор эндпоинтов

Срез MVP: библиотека клинреков → протокол → проверка → отчёт.
Каждый вердикт обязан ссылаться на чанк клинрека; `confidence < 0.6` → пункт уходит в «Требует внимания».

Обозначения: ✅ реализовано, 🚧 план (контракт согласован, кода нет).

Базовый префикс — `/api`. Схемы — Pydantic (`app/schemas/`). Ошибки — `{"detail": ...}`
(строка для 4xx-валидации, объект для 409).

---

## Служебное

### ✅ `GET /health`

Liveness-проба для Docker healthcheck и compose. Без обращений к БД и Qdrant.

| | Схема | Поля |
|---|---|---|
| Вход | — | — |
| Выход 200 | `HealthResponse` | `status: "ok"`, `version: str` |

Реализация: [app/routers/health.py](app/routers/health.py).

---

## Библиотека клинреков

Ingestion асинхронный: загрузка → парсинг PDF → иерархический чанкинг → embeddings → Qdrant.

### ✅ `POST /api/guidelines`

Загрузка PDF клинрека. Файл пишется потоково (чанки 1 МБ) в `STORAGE_DIR/guidelines/<guideline_id>/original.pdf`,
рядом `meta.json`. После успеха клинрек создан со статусом `uploaded`; запуск ingestion — отдельный шаг (план).

| | Схема | Поля |
|---|---|---|
| Вход (multipart/form-data) | `file: UploadFile` (обязательно), `title: str \| None` | PDF, ≤ `MAX_UPLOAD_SIZE_MB` |
| Выход 201 | `Guideline` | `guideline_id: UUID`, `version: int ≥1`, `title: str`, `filename: str`, `size_bytes: int`, `sha256: str(64)`, `status: GuidelineStatus`, `created_at: datetime`, `error: str \| None` |
| Ошибка 400 | `detail: str` | не PDF / пустой файл / нет имени |
| Ошибка 409 | `detail: {message, guideline_id}` | `sha256` уже загружен (дедупликация) |
| Ошибка 413 | `detail: str` | превышен `MAX_UPLOAD_SIZE_MB` |

`GuidelineStatus` = `uploaded` \| `processing` \| `ready` \| `failed`.
Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/schemas/guideline.py](app/schemas/guideline.py), [app/services/guidelines.py](app/services/guidelines.py).

### 🚧 `GET /api/guidelines`

Список клинреков с текущим статусом — для экрана Library.

| | Схема | Поля |
|---|---|---|
| Вход | query: `status: GuidelineStatus \| None`, `limit: int = 50`, `offset: int = 0` | фильтр и пагинация |
| Выход 200 | `list[Guideline]` | как выше |

### 🚧 `GET /api/guidelines/{guideline_id}`

Метаданные одного клинрека и прогресс индексации (для опроса после загрузки).

| | Схема | Поля |
|---|---|---|
| Вход | path: `guideline_id: UUID` | |
| Выход 200 | `Guideline` | `status`, `error` — состояние ingestion |
| Ошибка 404 | `detail: str` | клинрек не найден |

### 🚧 `GET /api/guidelines/{guideline_id}/file`

Оригинальный PDF для PDF.js (источник подсветки чанков).

| | Схема | Поля |
|---|---|---|
| Вход | path: `guideline_id: UUID`, query: `version: int \| None` (по умолчанию последняя) | |
| Выход 200 | `application/pdf` | `Content-Disposition: inline`, поддержка Range |
| Ошибка 404 | `detail: str` | нет файла или версии |

### 🚧 `GET /api/chunks/{chunk_id}`

Фрагмент клинрека по идентификатору из вердикта: текст, страница, координаты для подсветки.

| | Схема | Поля |
|---|---|---|
| Вход | path: `chunk_id: str` | |
| Выход 200 | `Chunk` | `chunk_id: str`, `guideline_id: UUID`, `guideline_version: int`, `page: int ≥1`, `section: str \| None`, `text: str`, `bbox: tuple[float, float, float, float] \| None` |
| Ошибка 404 | `detail: str` | чанк не найден |

Инвариант: `chunk_id` из вердикта всегда резолвится в существующий чанк своей версии документа.

---

## Протокол и проверка

### 🚧 `POST /api/protocols`

Создание протокола из структурированной формы с привязкой к версии клинрека.

| | Схема | Поля |
|---|---|---|
| Вход (JSON) | `ProtocolCreate` | `guideline_id: UUID`, `guideline_version: int \| None` (по умолчанию последняя), `form: ProtocolForm` |
| Выход 201 | `Protocol` | `protocol_id: UUID`, `guideline_id: UUID`, `guideline_version: int`, `form: ProtocolForm`, `created_at: datetime` |
| Ошибка 400 | `detail: str` | пустая форма / нет обязательных пунктов |
| Ошибка 404 | `detail: str` | клинрек или версия не найдены |

`ProtocolForm` (минимальный набор пунктов): `icd_code`, `complaints`, `anamnesis`, `diagnosis`,
`examinations: list[str]`, `treatment: list[str]`, `recommendations: list[str]` — все `str` / `list[str]`.

### 🚧 `POST /api/protocols/{protocol_id}/checks`

Запуск проверки протокола против клинрека (RAG + LLM, до ~30 с) — асинхронно.

| | Схема | Поля |
|---|---|---|
| Вход | path: `protocol_id: UUID` | тело не требуется |
| Выход 202 | `CheckAccepted` | `check_id: UUID`, `status: CheckStatus` = `pending` |
| Ошибка 404 | `detail: str` | протокол не найден |
| Ошибка 409 | `detail: str` | клинрек не в статусе `ready` / проверка уже идёт |

### 🚧 `GET /api/checks/{check_id}`

Статус проверки — опрос до получения `report_id`.

| | Схема | Поля |
|---|---|---|
| Вход | path: `check_id: UUID` | |
| Выход 200 | `CheckStatusResponse` | `check_id: UUID`, `status: CheckStatus`, `report_id: UUID \| None`, `error: str \| None` |
| Ошибка 404 | `detail: str` | проверка не найдена |

`CheckStatus` = `pending` \| `running` \| `done` \| `failed`.

### 🚧 `GET /api/reports/{report_id}`

Отчёт по протоколу: сводка, таблица пунктов с вердиктами и блок «Требует внимания».

| | Схема | Поля |
|---|---|---|
| Вход | path: `report_id: UUID` | |
| Выход 200 | `Report` | `report_id: UUID`, `protocol_id: UUID`, `guideline_id: UUID`, `guideline_version: int`, `created_at: datetime`, `summary: str`, `verdicts: list[Verdict]`, `needs_attention: list[Verdict]` |
| Ошибка 404 | `detail: str` | отчёт не найден |

`Verdict`: `verdict_id: UUID`, `item: str` (пункт протокола), `verdict: VerdictKind`, `comment: str`,
`chunk_id: str` (обязателен), `confidence: float` (0..1), `needs_attention: bool`.

`VerdictKind` = `match` \| `warning` \| `mismatch` \| `not_covered`.
Валидация на выходе: вердикт без `chunk_id` не сериализуется; `confidence < 0.6` → `needs_attention: true`
и дублирование в `needs_attention`.

### 🚧 `GET /api/reports`

История проверок для экрана History.

| | Схема | Поля |
|---|---|---|
| Вход | query: `limit: int = 50`, `offset: int = 0`, `guideline_id: UUID \| None` | пагинация и фильтр |
| Выход 200 | `list[ReportListItem]` | `report_id: UUID`, `protocol_id: UUID`, `created_at: datetime`, `verdicts_total: int`, `needs_attention_total: int` |

---

## Общие схемы

| Схема | Назначение |
|---|---|
| `HealthResponse` | ответ `/health` |
| `Guideline`, `GuidelineStatus` | клинрек и его состояние в ingestion |
| `Chunk` | фрагмент клинрека для цитаты и подсветки |
| `ProtocolCreate`, `Protocol`, `ProtocolForm` | вход и хранение протокола |
| `CheckAccepted`, `CheckStatusResponse`, `CheckStatus` | асинхронная проверка |
| `Report`, `Verdict`, `VerdictKind`, `ReportListItem` | результат проверки и история |

---

## Вне минимального набора

Вторично по README, контракт не фиксируем до реализации ядра:

- `POST /api/verdicts/{verdict_id}/feedback` — 👍/👎 на вердикт;
- `POST /api/protocols/{protocol_id}/chat` и `GET .../chat` — уточняющие вопросы с цитатами;
- `GET /api/reports/{report_id}/export/pdf` — экспорт отчёта;
- `PUT /api/protocols/{protocol_id}` — правка черновика.
