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

Ingestion асинхронный: загрузка → извлечение текста и геометрии → иерархический чанкинг →
эмбеддинги → Qdrant. Он запускается автоматически после ответа на загрузку, а прогресс и итог
видны в полях `Guideline`.

### ✅ `POST /api/guidelines`

Загрузка PDF клинрека. Файл пишется потоково (чанки по 1 МБ) в
`STORAGE_DIR/guidelines/<guideline_id>/original.pdf`, рядом кладётся `meta.json`.
После успеха клинрек создан со статусом `uploaded`, и сразу после ответа запускается
индексация: клинрек переходит в `processing`, а затем в `ready` или `failed`.

**Вход** — `multipart/form-data`

- `file` (`UploadFile`, обязательно) — PDF, не больше `MAX_UPLOAD_SIZE_MB`
- `title` (`str | None`) — название клинрека; по умолчанию имя файла без расширения
- `icd_codes` (`list[str]`, обязательно) — коды МКБ-10, которые покрывает клинрек; поле
  повторяется, минимум одно значение. Коды нормализуются: обрезка пробелов, верхний регистр,
  без повторов; формат `^[A-Z]\d{2}(\.\d{1,2})?$` (`I10`, `I10.1`)

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
  "error": null,
  "icd_codes": ["I10", "I15"],
  "chunks_total": null,
  "chunks_indexed": null,
  "embedding_model": null,
  "indexed_at": null
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
- `error` (`str | null`) — причина отказа индексации при `status = failed`
- `icd_codes` (`list[str]`) — коды МКБ-10, которые покрывает клинрек, нормализованные
- `chunks_total` (`int | null`, ≥ 0) — сколько фрагментов получилось при индексации
- `chunks_indexed` (`int | null`, ≥ 0) — сколько фрагментов уже записано: ход индексации
- `embedding_model` (`str | null`) — модель, которой посчитаны векторы этого клинрека
- `indexed_at` (`datetime | null`, UTC) — когда индексация завершилась

Поля индексации необязательны: манифесты, записанные до её появления, читаются как есть, а
`status = uploaded` означает, что индексация ещё не запускалась. `icd_codes` при чтении тоже
необязательно: манифест без кодов читается как пустой список, но создать клинрек без кода нельзя.

**Значения `GuidelineStatus`**

- `uploaded` — файл сохранён, индексация ещё не начиналась
- `processing` — идёт извлечение текста, чанкинг и запись векторов
- `ready` — клинрек векторизован и готов к проверкам
- `failed` — индексация упала, причина в `error`; доступен повтор

**Ошибки**

- `400` — файл пустой, не PDF (нет сигнатуры `%PDF-`), не передано имя или нет ни одного кода
  МКБ (`at least one ICD code is required`, `invalid ICD code: ...`)
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
- `icd` (`str | None`) — фильтр по коду МКБ-10. Сопоставление учитывает уточнение: клинрек с
  кодом `I10` попадает и под фильтр `I10.1`, а `I1` не совпадает ни с чем. Регистр не важен;
  код вне формата → `422`
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
    "error": null,
    "icd_codes": ["I10", "I15"]
  }
]
```

Схема элемента — `Guideline` (см. выше). Порядок — от свежих загрузок к старым.

**Ошибки**

- `422` — некорректные query-параметры, включая код МКБ вне формата

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

### ✅ `POST /api/guidelines/{guideline_id}/index`

Запуск индексации клинрека. Нужен после отказа: без повтора клинрек в `failed` остаётся
необработанным, и его фрагменты нельзя процитировать.

**Вход** — path-параметр

- `guideline_id` (`UUID`) — идентификатор клинрека

**Выход `202 Accepted`** — `Guideline` со статусом `processing`

Индексация выполняется в фоне; ход виден по `chunks_indexed` и `chunks_total`, итог — по `status`.

**Ошибки**

- `404` — клинрек не найден
- `409` — индексация этого клинрека уже идёт

### ✅ `DELETE /api/guidelines/{guideline_id}`

Удаление клинрека целиком: оригинал PDF, `meta.json` и все его фрагменты в векторном хранилище.
Порядок — сначала фрагменты, затем файлы: если хранилище недоступно, клинрек остаётся целым и в
библиотеке, а не превращается в набор чанков без документа, на который нельзя сослаться.

**Вход** — path-параметр

- `guideline_id` (`UUID`) — идентификатор клинрека

**Выход `204 No Content`** — без тела

**Ошибки**

- `404` — клинрек не найден, в том числе при повторном удалении
- `409` — по клинреку идёт индексация: удаление станет доступно после её окончания
- `503` — векторное хранилище недоступно; файлы и метаданные при этом не тронуты

Реализация: [app/routers/guidelines.py](app/routers/guidelines.py), [app/runtime.py](app/runtime.py), [app/services/guidelines.py](app/services/guidelines.py).

### ✅ `GET /api/chunks/{chunk_id}`

Фрагмент клинрека по идентификатору из вердикта: текст цитаты, раздел и геометрия подсветки.

**Вход** — path-параметр

- `chunk_id` (`UUID`) — идентификатор фрагмента, пришедший в вердикте

**Выход `200 OK`** — `Chunk`

```json
{
  "chunk_id": "5c1f7a90-2b4d-4f6e-9a11-8d3c0e5b7f42",
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "section": "2.4. Оценка сердечно-сосудистого риска",
  "text": "Всем пациентам с АГ рекомендуется измерение АД на обеих руках...",
  "chunk_index": 128,
  "page": 18,
  "bbox": [72.0, 480.5, 512.0, 496.25],
  "rects": [
    { "page": 18, "bbox": [72.0, 480.5, 512.0, 496.25] },
    { "page": 19, "bbox": [72.0, 96.0, 512.0, 240.75] }
  ]
}
```

**Поля `Chunk`**

- `chunk_id` (`UUID`) — детерминированный идентификатор фрагмента
- `guideline_id` (`UUID`) — клинрек-источник
- `guideline_version` (`int`, ≥ 1) — версия документа на момент чанкинга
- `section` (`str | null`) — заголовок раздела, внутри которого лежит фрагмент
- `text` (`str`) — текст фрагмента, то есть цитата в вердикте
- `chunk_index` (`int`, ≥ 0) — порядковый номер фрагмента в документе
- `page` (`int`, ≥ 1) — страница первого прямоугольника
- `bbox` (`[float, float, float, float] | null`) — первый прямоугольник подсветки
- `rects` (`list[ChunkRect]`) — по прямоугольнику на каждую страницу фрагмента

Фрагмент режется по смыслу и не обязан укладываться в одну страницу: замер на клинреке
«Гипертензия» дал 13 % фрагментов на двух и более страницах, поэтому подсветка описывается
списком прямоугольников, а `page`/`bbox` оставлены первым из них для совместимости.

**Поля `ChunkRect`**

- `page` (`int`, ≥ 1) — страница PDF
- `bbox` (`[float, float, float, float]`) — границы фрагмента на этой странице

Координаты — в системе страницы PDF без учёта её поворота: именно их принимает
`viewport.convertToViewportPoint` в PDF.js. Для страниц с `/Rotate` координаты приводятся
обратно к неразвёрнутой странице.

**Ошибки**

- `404` — фрагмент не найден
- `503` — векторное хранилище недоступно

Реализация: [app/routers/chunks.py](app/routers/chunks.py), [app/clients/vector_store.py](app/clients/vector_store.py).

Инвариант: `chunk_id` из вердикта всегда резолвится в существующий чанк своей версии документа.
Идентификаторы детерминированы, поэтому повторная индексация не осиротит ссылки в уже выданных
отчётах.

---

## Протокол и проверка

### ✅ `POST /api/protocols/validate`

Проверка черновика протокола: сервер валидирует форму, подтверждает выбранный клинрек и
возвращает атомарные пункты, которые пойдут в проверку. **Ничего не сохраняет** — идентификатора
протокола в ответе нет, черновик живёт только в интерфейсе. Создание протокола и сама проверка на
соответствие клинреку — следующие изменения.

**Вход** — `application/json`, схема `ProtocolDraftRequest`

```json
{
  "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
  "guideline_version": 1,
  "form": {
    "complaints": "Головная боль, головокружение",
    "diagnosis": { "code": "I10", "name": "Гипертензия" },
    "diagnosis_description": "АГ 2 ст., риск 3",
    "prescriptions": [
      { "kind": "drug", "name": "Амлодипин", "dose": "5 мг", "frequency": "1 раз в сутки" },
      { "kind": "procedure", "name": "ЭКГ" }
    ]
  }
}
```

**Поля `ProtocolDraftRequest`**

- `guideline_id` (`UUID`) — клинрек, по которому будет проверка
- `guideline_version` (`int | null`, ≥ 1) — версия документа; по умолчанию последняя
- `form` (`ProtocolForm`) — заполненная форма

**Поля `ProtocolForm`**

- `complaints` (`str`) — жалобы, обязательны, до 5000 символов
- `diagnosis` (`IcdDiagnosis`) — код МКБ-10 и название диагноза
- `diagnosis_description` (`str | null`) — описание диагноза, до 5000 символов
- `prescriptions` (`list[ProtocolPrescription]`) — назначения отдельными пунктами, до 50

**Поля `IcdDiagnosis`**

- `code` (`str`) — код МКБ-10 в формате `^[A-Z]\d{2}(\.\d{1,2})?$`; нормализуется
- `name` (`str`) — название диагноза, до 300 символов

**Поля `ProtocolPrescription`**

- `kind` (`"drug" | "procedure"`) — вид назначения
- `name` (`str`) — название препарата или процедуры, до 300 символов
- `dose`, `frequency`, `duration` (`str | null`) — до 100 символов каждый; разрешены только для
  `drug`, у `procedure` приводят к `400`

**Выход `200 OK`** — `ProtocolDraftResponse`

```json
{
  "guideline": {
    "guideline_id": "a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7",
    "version": 1,
    "title": "Гипертензия",
    "status": "ready",
    "icd_codes": ["I10", "I15"]
  },
  "form": {
    "complaints": "Головная боль, головокружение",
    "diagnosis": { "code": "I10", "name": "Гипертензия" },
    "diagnosis_description": "АГ 2 ст., риск 3",
    "prescriptions": [
      { "kind": "drug", "name": "Амлодипин", "dose": "5 мг", "frequency": "1 раз в сутки" },
      { "kind": "procedure", "name": "ЭКГ" }
    ]
  },
  "statements": [
    "Жалобы: Головная боль, головокружение",
    "Диагноз: I10 — Гипертензия",
    "Описание диагноза: АГ 2 ст., риск 3",
    "Назначение: Амлодипин, 5 мг, 1 раз в сутки",
    "Процедура: ЭКГ"
  ]
}
```

**Поля `ProtocolDraftResponse`**

- `guideline` (`ProtocolGuidelineRef`) — подтверждённый клинрек: идентификатор, версия, название,
  статус и коды МКБ
- `form` (`ProtocolForm`) — нормализованная форма: код МКБ в верхнем регистре, краевые пробелы сняты
- `statements` (`list[str]`) — атомарные пункты в детерминированном порядке: жалобы, диагноз,
  описание (если заполнено), затем по одному пункту на каждое назначение

**Ошибки**

- `400` — форма отклонена; в `detail` названо поле, например
  `diagnosis.code: expected ICD-10 code, for example I10`
- `404` — клинрек или указанная версия не найдены
- `409` — клинрек не в статусе `ready`; в `detail` его текущий статус

Реализация: [app/routers/protocols.py](app/routers/protocols.py), [app/schemas/protocol.py](app/schemas/protocol.py), [app/services/protocols.py](app/services/protocols.py).

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

## Чат по клинрекам

### ✅ `POST /api/chat/ask`

Вопрос врача по выбранным клинрекам. Ответ строится только по фрагментам выбранных
документов, каждый факт помечен ссылкой на фрагмент. Лента диалога не хранится: каждая
реплика — отдельный запрос, история влияет только на поисковый запрос.

**Вход** — `application/json`, схема `ChatAskRequest`

```json
{
  "guideline_ids": ["7434ecc7-58ec-4925-9b93-cb4d507646ca"],
  "question": "А если ещё и диабет, до какого давления снижать?",
  "history": [
    { "role": "user", "text": "До какого давления снижать пациенту 60 лет?" },
    { "role": "assistant", "text": "Снижать до 140/90 [1].", "citations": [{ "chunk_id": "4f1d6e2a-…" }] }
  ]
}
```

**Поля `ChatAskRequest`**

- `guideline_ids` (`list[UUID]`) — документы, по которым разрешено искать; дубли снимаются,
  больше `CHAT_MAX_GUIDELINES` — отказ
- `question` (`str`) — вопрос целиком, до 2000 символов
- `history` (`list[ChatMessage]`) — лента; прошлые цитаты не используются, на поисковый
  запрос влияют последние `CHAT_HISTORY_WINDOW` сообщений

**Выход `200 OK`** — `ChatAnswer`

```json
{
  "status": "answered",
  "answer": "Снижать до 140/90 мм рт. ст. [1]; при хорошей переносимости — 130/80 [2].",
  "citations": [
    {
      "n": 1,
      "chunk_id": "4f1d6e2a-1111-4222-8333-944455556666",
      "guideline_id": "7434ecc7-58ec-4925-9b93-cb4d507646ca",
      "guideline_version": 1,
      "guideline_title": "Гипертензия",
      "section": "3.2. Целевые уровни",
      "page": 9,
      "quote": "Целевой уровень АД — ниже 140/90 мм рт. ст."
    }
  ],
  "search": { "expression": "целевой уровень АД у пациента 60 лет с диабетом", "rewritten": true, "constraints_lost": 0 },
  "searched_guidelines": [
    { "guideline_id": "7434ecc7-58ec-4925-9b93-cb4d507646ca", "title": "Гипертензия", "version": 1 }
  ]
}
```

**Поля `ChatAnswer`**

- `status` (`ChatStatus`) — `answered` или `not_found`
- `answer` (`str | null`) — текст с маркерами `[n]`; маркер без подтверждённой ссылки удалён
- `citations` (`list[Citation]`) — только подтверждённые ссылки: номер, фрагмент, документ,
  версия, раздел, страница и дословная цитата
- `search` (`SearchInfo`) — запрос, ушедший в поиск, признак переписывания и число
  потерянных условий
- `searched_guidelines` (`list[ChatGuidelineRef]`) — документы, по которым шёл поиск

**Отказ по существу вопроса** — тот же `200 OK`:

```json
{
  "status": "not_found",
  "answer": null,
  "citations": [],
  "search": { "expression": "доза аллопуринола при подагре", "rewritten": true, "constraints_lost": 0 },
  "searched_guidelines": [{ "guideline_id": "7434ecc7-…", "title": "Гипертензия", "version": 1 }]
}
```

Текст модели без подтверждённых ссылок не отдаётся: отказ — это пустой `citations`, а не
пересказ.

**Ошибки**

- `400` — пустой вопрос, не выбран ни один документ, документов больше предела
- `404` — клинрек не найден
- `409` — клинрек не в статусе `ready`
- `502` — LLM недоступна, отказала или ответ не соответствует схеме
- `503` — векторное хранилище недоступно

Реализация: [app/routers/chat.py](app/routers/chat.py), [app/services/chat.py](app/services/chat.py), [app/schemas/chat.py](app/schemas/chat.py).

---

## Общие схемы

- `HealthResponse` — ответ `/health`
- `Guideline`, `GuidelineStatus` — клинрек и его состояние в ingestion
- `Chunk` — фрагмент клинрека для цитаты и подсветки
- `ChatAskRequest`, `ChatAnswer`, `Citation`, `SearchInfo`, `ChatGuidelineRef`, `ChatMessage` — чат по клинрекам
- `ProtocolDraftRequest`, `ProtocolDraftResponse`, `ProtocolGuidelineRef` — валидация черновика
- `ProtocolForm`, `IcdDiagnosis`, `ProtocolPrescription` — форма протокола и её части
- `ProtocolCreate`, `Protocol` — создание и хранение протокола (план)
- `CheckAccepted`, `CheckStatusResponse`, `CheckStatus` — асинхронная проверка
- `Report`, `Verdict`, `VerdictKind`, `ReportListItem` — результат проверки и история

---

## Вне минимального набора

Вторично по README, контракт не фиксируем до реализации ядра:

- `POST /api/verdicts/{verdict_id}/feedback` — 👍/👎 на вердикт
- `GET /api/reports/{report_id}/export/pdf` — экспорт отчёта
- `PUT /api/protocols/{protocol_id}` — правка черновика

Чат по документам уже реализован (`POST /api/chat/ask`); уточняющие вопросы, привязанные к
сохранённому протоколу, появятся вместе с проверкой протокола.
