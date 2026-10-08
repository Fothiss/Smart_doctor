# API — минимальный набор эндпоинтов

Срез MVP: библиотека клинреков → протокол → проверка → отчёт.
Каждый вердикт обязан ссылаться на чанк клинрека; `confidence < 0.6` → пункт уходит в «Требует внимания».

Обозначения:

- ✅ реализовано
- 🚧 план (контракт согласован, кода нет)

Базовый префикс — `/api`. Схемы — Pydantic (`app/schemas/`). Формат ошибок — `{"detail": ...}`:
строка для 4xx-валидации, объект для `409`.

---

## Служебное

### ✅ `GET /health`

Liveness-проба для Docker healthcheck и compose. Обращений к БД и Qdrant нет.

**Вход** — нет.

**Выход `200 OK`** — `HealthResponse`

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

**Поля `HealthResponse`**

- `status` (`"ok"`) — всегда `ok`, если процесс жив
- `version` (`str`) — версия приложения

Реализация: [app/routers/health.py](app/routers/health.py).

---

## Библиотека клинреков

Ingestion асинхронный: загрузка → парсинг PDF → иерархический чанкинг → embeddings → Qdrant.

### ✅ `POST /api/guidelines`

Загрузка PDF клинрека. Файл пишется потоково (чанки по 1 МБ) в
`STORAGE_DIR/guidelines/<guideline_id>/original.pdf`, рядом кладётся `meta.json`.
После успеха клинрек создан со статусом `uploaded`; запуск ingestion — отдельный шаг (план).

**Вход** — `multipart/form-data`

- `file` (`UploadFile`, обязательно) — PDF, не больше `MAX_UPLOAD_SIZE_MB`
- `title` (`str | None`) — название клинрека; по умолчанию имя файла без расширения

**Выход `201 Created`** — `Guideline`

```json
{
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "version": 1,
  "title": "Гипертензия",
  "filename": "КР62_3.pdf",
  "size_bytes": 3202485,
  "sha256": "b10d1f1df988056b5be83380e9be72ca4af6056deecfa93dd06dc84ca1e2afe3",
  "status": "uploaded",
  "created_at": "2026-10-08T08:30:05.429862Z",
  "error": null
}
```

**Поля `Guideline`**

- `guideline_id` (`UUID`) — идентификатор клинрека
- `version` (`int`, ≥ 1) — версия документа; старые отчёты привязаны к своей версии
- `title` (`str`) — название
- `filename` (`str`) — исходное имя загруженного файла
- `size_bytes` (`int`, ≥ 0) — размер PDF в байтах
- `sha256` (`str`, 64 символа) — хеш содержимого, используется для дедупликации
- `status` (`GuidelineStatus`) — состояние в пайплайне ingestion
- `created_at` (`datetime`, UTC) — момент загрузки
- `error` (`str | null`) — причина падения ingestion при `status = failed`

**Значения `GuidelineStatus`**

- `uploaded` — файл сохранён, ingestion не запускался
- `processing` — идёт парсинг, чанкинг, индексация
- `ready` — клинрек готов к проверкам
- `failed` — ingestion упал, причина в `error`

**Ошибки**

- `400` — файл пустой, не PDF (нет сигнатуры `%PDF-`) или не передано имя
- `409` — PDF с таким же `sha256` уже загружен:
  ```json
  {
    "detail": {
      "message": "guideline with the same content already exists",
      "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7"
    }
  }
  ```
- `413` — размер превышает `MAX_UPLOAD_SIZE_MB`

Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/schemas/guideline.py](app/schemas/guideline.py), [app/services/guidelines.py](app/services/guidelines.py).

### ✅ `GET /api/guidelines`

Список клинреков с текущим статусом — для экрана Library.

**Вход** — query-параметры

- `status` (`GuidelineStatus | None`) — фильтр по состоянию
- `limit` (`int`, по умолчанию 50) — размер страницы
- `offset` (`int`, по умолчанию 0) — смещение

**Выход `200 OK`** — `list[Guideline]`

```json
[
  {
    "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
    "version": 1,
    "title": "Гипертензия",
    "filename": "КР62_3.pdf",
    "size_bytes": 3202485,
    "sha256": "b10d1f1df988056b5be83380e9be72ca4af6056deecfa93dd06dc84ca1e2afe3",
    "status": "ready",
    "created_at": "2026-10-08T08:30:05.429862Z",
    "error": null
  }
]
```

Схема элемента — `Guideline` (см. выше). Порядок — от свежих загрузок к старым.

Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/services/guidelines.py](app/services/guidelines.py).

### ✅ `GET /api/guidelines/{guideline_id}`

Метаданные одного клинрека и прогресс индексации — для опроса после загрузки.

**Вход** — path-параметр

- `guideline_id` (`UUID`) — идентификатор клинрека

**Выход `200 OK`** — `Guideline`

```json
{
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "version": 1,
  "title": "Гипертензия",
  "filename": "КР62_3.pdf",
  "size_bytes": 3202485,
  "sha256": "b10d1f1df988056b5be83380e9be72ca4af6056deecfa93dd06dc84ca1e2afe3",
  "status": "processing",
  "created_at": "2026-10-08T08:30:05.429862Z",
  "error": null
}
```

**Ошибки**

- `404` — клинрек не найден

Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/services/guidelines.py](app/services/guidelines.py).

### ✅ `GET /api/guidelines/{guideline_id}/file`

Оригинальный PDF для PDF.js — источник подсветки чанков.

**Вход**

- path: `guideline_id` (`UUID`)
- query: `version` (`int | None`) — версия документа, по умолчанию последняя

**Выход `200 OK`** — бинарный поток

- `Content-Type: application/pdf`
- `Content-Disposition: inline; filename="КР62_3.pdf"`
- поддержка `Range` — PDF.js докачивает страницы частями

**Ошибки**

- `404` — клинрек или указанная версия не найдены

Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/services/guidelines.py](app/services/guidelines.py).

### 🚧 `GET /api/chunks/{chunk_id}`

Фрагмент клинрека по идентификатору из вердикта: текст, страница, координаты для подсветки.

**Вход** — path-параметр

- `chunk_id` (`str`) — идентификатор чанка, пришедший в вердикте

**Выход `200 OK`** — `Chunk`

```json
{
  "chunk_id": "5c1f7a90-2b4d-4f6e-9a11-8d3c0e5b7f42",
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "page": 12,
  "section": "Диагностика",
  "text": "Всем пациентам с АГ рекомендуется измерение АД на обеих руках...",
  "bbox": [72.0, 480.5, 512.0, 496.25]
}
```

**Поля `Chunk`**

- `chunk_id` (`str`) — идентификатор чанка
- `guideline_id` (`UUID`) — клинрек-источник
- `guideline_version` (`int`) — версия документа на момент чанкинга
- `page` (`int`, ≥ 1) — страница PDF
- `section` (`str | null`) — заголовок раздела иерархии
- `text` (`str`) — текст фрагмента, то есть цитата в вердикте
- `bbox` (`[float, float, float, float] | null`) — координаты подсветки на странице

**Ошибки**

- `404` — чанк не найден

Инвариант: `chunk_id` из вердикта всегда резолвится в существующий чанк своей версии документа.

---

## Протокол и проверка

### 🚧 `POST /api/protocols`

Создание протокола из структурированной формы с привязкой к версии клинрека.

**Вход** — `application/json`, схема `ProtocolCreate`

```json
{
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "form": {
    "icd_code": "I10",
    "complaints": "Головная боль, головокружение",
    "anamnesis": "Повышение АД в течение 5 лет",
    "diagnosis": "Гипертензия",
    "examinations": ["ЭКГ", "ОАК", "креатинин"],
    "treatment": ["амлодипин 5 мг/сут"],
    "recommendations": ["контроль АД дважды в день"]
  }
}
```

**Поля `ProtocolCreate`**

- `guideline_id` (`UUID`) — клинрек, по которому проверяем
- `guideline_version` (`int | None`) — версия клинрека; по умолчанию последняя
- `form` (`ProtocolForm`) — содержимое формы протокола

**Поля `ProtocolForm`**

- `icd_code` (`str`) — код МКБ
- `complaints` (`str`) — жалобы
- `anamnesis` (`str`) — анамнез
- `diagnosis` (`str`) — диагноз
- `examinations` (`list[str]`) — обследования
- `treatment` (`list[str]`) — лечение
- `recommendations` (`list[str]`) — рекомендации

**Выход `201 Created`** — `Protocol`

```json
{
  "protocol_id": "0f9c2d31-6a44-4c8b-9d0e-27b5f1a8c3de",
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "form": {
    "icd_code": "I10",
    "complaints": "Головная боль, головокружение",
    "anamnesis": "Повышение АД в течение 5 лет",
    "diagnosis": "Гипертензия",
    "examinations": ["ЭКГ", "ОАК", "креатинин"],
    "treatment": ["амлодипин 5 мг/сут"],
    "recommendations": ["контроль АД дважды в день"]
  },
  "created_at": "2026-10-08T09:02:11.104523Z"
}
```

**Поля `Protocol`**

- `protocol_id` (`UUID`) — идентификатор протокола
- `guideline_id` (`UUID`) — привязанный клинрек
- `guideline_version` (`int`) — зафиксированная версия клинрека
- `form` (`ProtocolForm`) — сохранённая форма
- `created_at` (`datetime`, UTC) — момент создания

**Ошибки**

- `400` — пустая форма или нет обязательных пунктов
- `404` — клинрек или указанная версия не найдены

### 🚧 `POST /api/protocols/{protocol_id}/checks`

Запуск проверки протокола против клинрека (RAG + LLM, до ~30 с). Выполняется асинхронно:
ответ приходит сразу, результат забирается опросом `GET /api/checks/{check_id}`.

**Вход**

- path: `protocol_id` (`UUID`)
- тело запроса: не требуется

**Выход `202 Accepted`** — `CheckAccepted`

```json
{
  "check_id": "b7d4e0a2-1c35-4e79-8f60-9a2b3c4d5e6f",
  "status": "pending"
}
```

**Поля `CheckAccepted`**

- `check_id` (`UUID`) — идентификатор запущенной проверки
- `status` (`CheckStatus`) — всегда `pending` в ответе на запуск

**Ошибки**

- `404` — протокол не найден
- `409` — клинрек не в статусе `ready` либо проверка по этому протоколу уже идёт

### 🚧 `GET /api/checks/{check_id}`

Статус проверки — опрос до появления `report_id`.

**Вход** — path-параметр

- `check_id` (`UUID`) — идентификатор проверки

**Выход `200 OK`** — `CheckStatusResponse`

```json
{
  "check_id": "b7d4e0a2-1c35-4e79-8f60-9a2b3c4d5e6f",
  "status": "done",
  "report_id": "c8e5f1b3-2d46-4f8a-9b71-0c3d4e5f6a7b",
  "error": null
}
```

**Поля `CheckStatusResponse`**

- `check_id` (`UUID`) — идентификатор проверки
- `status` (`CheckStatus`) — состояние
- `report_id` (`UUID | null`) — отчёт, заполнен при `status = done`
- `error` (`str | null`) — причина при `status = failed`

**Значения `CheckStatus`**

- `pending` — задача создана, ещё не взята в работу
- `running` — идёт retrieval и вызов LLM
- `done` — отчёт готов, идентификатор в `report_id`
- `failed` — проверка упала, причина в `error`

**Ошибки**

- `404` — проверка не найдена

### 🚧 `GET /api/reports/{report_id}`

Отчёт по протоколу: сводка, таблица пунктов с вердиктами и блок «Требует внимания».

**Вход** — path-параметр

- `report_id` (`UUID`) — идентификатор отчёта

**Выход `200 OK`** — `Report`

```json
{
  "report_id": "c8e5f1b3-2d46-4f8a-9b71-0c3d4e5f6a7b",
  "protocol_id": "0f9c2d31-6a44-4c8b-9d0e-27b5f1a8c3de",
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "created_at": "2026-10-08T09:02:41.882301Z",
  "summary": "4 из 5 пунктов соответствуют клинреку, 1 требует внимания",
  "verdicts": [
    {
      "verdict_id": "d9f6a2c4-3e57-4a9b-8c82-1d4e5f6a7b8c",
      "item": "Диагноз: Гипертензия",
      "verdict": "match",
      "comment": "Формулировка соответствует разделу «Диагностика»",
      "chunk_id": "5c1f7a90-2b4d-4f6e-9a11-8d3c0e5b7f42",
      "confidence": 0.87,
      "needs_attention": false
    },
    {
      "verdict_id": "e0a7b3d5-4f68-4b0c-9d93-2e5f6a7b8c9d",
      "item": "Обследования: ЭКГ, ОАК",
      "verdict": "not_covered",
      "comment": "В клинреке ЭКГ не указана как обязательная при неосложнённой АГ",
      "chunk_id": "7d2e8b01-3c56-4a7d-8e22-9f4b5c6d7e8f",
      "confidence": 0.54,
      "needs_attention": true
    }
  ],
  "needs_attention": [
    {
      "verdict_id": "e0a7b3d5-4f68-4b0c-9d93-2e5f6a7b8c9d",
      "item": "Обследования: ЭКГ, ОАК",
      "verdict": "not_covered",
      "comment": "В клинреке ЭКГ не указана как обязательная при неосложнённой АГ",
      "chunk_id": "7d2e8b01-3c56-4a7d-8e22-9f4b5c6d7e8f",
      "confidence": 0.54,
      "needs_attention": true
    }
  ]
}
```

**Поля `Report`**

- `report_id` (`UUID`) — идентификатор отчёта
- `protocol_id` (`UUID`) — проверенный протокол
- `guideline_id` (`UUID`) — клинрек-источник
- `guideline_version` (`int`) — версия клинрека на момент проверки
- `created_at` (`datetime`, UTC) — момент формирования отчёта
- `summary` (`str`) — текстовая сводка
- `verdicts` (`list[Verdict]`) — все пункты протокола
- `needs_attention` (`list[Verdict]`) — подмножество `verdicts` с `needs_attention = true`

**Поля `Verdict`**

- `verdict_id` (`UUID`) — идентификатор вердикта, нужен для feedback
- `item` (`str`) — атомарное утверждение из протокола
- `verdict` (`VerdictKind`) — вердикт по пункту
- `comment` (`str`) — пояснение
- `chunk_id` (`str`, обязателен) — ссылка на чанк клинрека
- `confidence` (`float`, 0..1) — уверенность
- `needs_attention` (`bool`) — `true`, если `confidence < 0.6`

**Значения `VerdictKind`**

- `match` — соответствует
- `warning` — предупреждение
- `mismatch` — не соответствует
- `not_covered` — не покрыто клинреком

**Инварианты выхода**

- вердикт без `chunk_id` не сериализуется — это ошибка сервиса, а не допустимый ответ
- `confidence < 0.6` → `needs_attention = true` и дублирование пункта в `needs_attention`

**Ошибки**

- `404` — отчёт не найден

### 🚧 `GET /api/reports`

История проверок для экрана History.

**Вход** — query-параметры

- `limit` (`int`, по умолчанию 50) — размер страницы
- `offset` (`int`, по умолчанию 0) — смещение
- `guideline_id` (`UUID | None`) — фильтр по клинреку

**Выход `200 OK`** — `list[ReportListItem]`

```json
[
  {
    "report_id": "c8e5f1b3-2d46-4f8a-9b71-0c3d4e5f6a7b",
    "protocol_id": "0f9c2d31-6a44-4c8b-9d0e-27b5f1a8c3de",
    "created_at": "2026-10-08T09:02:41.882301Z",
    "verdicts_total": 5,
    "needs_attention_total": 1
  }
]
```

**Поля `ReportListItem`**

- `report_id` (`UUID`) — идентификатор отчёта
- `protocol_id` (`UUID`) — проверенный протокол
- `created_at` (`datetime`, UTC) — когда сделана проверка
- `verdicts_total` (`int`) — всего пунктов
- `needs_attention_total` (`int`) — пунктов в «Требует внимания»

---

## Общие схемы

- `HealthResponse` — ответ `/health`
- `Guideline`, `GuidelineStatus` — клинрек и его состояние в ingestion
- `Chunk` — фрагмент клинрека для цитаты и подсветки
- `ProtocolCreate`, `Protocol`, `ProtocolForm` — вход и хранение протокола
- `CheckAccepted`, `CheckStatusResponse`, `CheckStatus` — асинхронная проверка
- `Report`, `Verdict`, `VerdictKind`, `ReportListItem` — результат проверки и история

---

## Вне минимального набора

Вторично по README, контракт не фиксируем до реализации ядра:

- `POST /api/verdicts/{verdict_id}/feedback` — 👍/👎 на вердикт
- `POST /api/protocols/{protocol_id}/chat` и `GET /api/protocols/{protocol_id}/chat` — уточняющие вопросы с цитатами
- `GET /api/reports/{report_id}/export/pdf` — экспорт отчёта
- `PUT /api/protocols/{protocol_id}` — правка черновика
