# Frontend (Smart Doctor SPA)

React + TypeScript SPA: библиотека клинреков и просмотр оригинала PDF.
См. корневой [README](../README.md), [AGENTS.md](../AGENTS.md) и контракт API в [backend/API.md](../backend/API.md).

## Быстрый старт

Бэкенд должен быть запущен на `127.0.0.1:8000` (см. [backend/README.md](../backend/README.md)).

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Vite слушает `localhost` (на Windows это IPv6), поэтому адрес `127.0.0.1:5173` не отвечает —
открывайте `http://localhost:5173`.

В PowerShell с политикой `AllSigned` файл `npm.ps1` не запускается — используйте `npm.cmd run dev`.

Vite проксирует `/api` на `127.0.0.1:8000` (см. `vite.config.ts`), поэтому приложение всегда
обращается к относительному `/api` и CORS не нужен. При смене `BACKEND_PORT`/`PORT` поправьте
`BACKEND_ORIGIN` в `vite.config.ts`.

## Скрипты

| Задача | Команда |
|---|---|
| Разработка | `npm run dev` |
| Сборка | `npm run build` |
| Просмотр собранной версии | `npm run preview` |
| Линт | `npm run lint` |
| Форматирование | `npm run format` |
| Тесты | `npm run test` |
| Типы из контракта | `npm run gen:api` |

`preview` тоже проксирует `/api`, поэтому собранную версию можно проверять без nginx. Полный путь
с nginx (`location /api/`) проверяется через `docker compose up -d --build frontend`.

## Слой API

```
src/api/
  schema.d.ts     типы, сгенерированные из ../openapi.json — руками не правятся
  client.ts       транспорт: getJson, ApiError, разбор {"detail": ...}
  guidelines.ts   обёртки эндпоинтов клинреков и типы Guideline / GuidelineStatus
```

- **`ApiError`** всегда несёт HTTP-статус и читаемое сообщение. Бэкенд отдаёт `detail` строкой
  (400/404/413), объектом `{message, guideline_id}` (409) и массивом (422) — `parseErrorDetail`
  понимает все три вида, поэтому в интерфейс не попадает `[object Object]`, а идентификатор
  дубликата не теряется.
- **Статус недоступного сервера** — `ApiError` со статусом `0`.
- **Загрузка файла** идёт через `XMLHttpRequest` (`uploadGuideline`): только он сообщает о ходе
  отправки, а PDF бывает до 50 МБ.

### Обновление типов

`openapi.json` лежит в корне репозитория и обновляется вместе с бэкендом. После изменения контракта:

```bash
npm run gen:api      # ../openapi.json → src/api/schema.d.ts
```

Сгенерированный файл коммитится: сборка не должна зависеть от запущенного бэкенда.

## Просмотрщик PDF

Экран `/library/<guideline_id>/view?page=N` показывает оригинал клинрека через `pdfjs-dist`.

- **Worker.** `pdfjs-dist/build/pdf.worker.min.mjs` импортируется через `?url`, поэтому Vite
  складывает его в `assets/` собранного бандла. Путь настраивается один раз в
  `src/hooks/usePdfDocument.ts` (`GlobalWorkerOptions.workerSrc`); копировать worker в `public/`
  не нужно. Если после сборки вместо страниц пустой экран — проверьте, что файл worker'а попал в
  `dist/assets/`.
- **Range.** Документ открывается по адресу `/api/guidelines/{id}/file`, и PDF.js запрашивает
  файл частями (`Range: bytes=...`). Сервер отвечает `206 Partial Content`; проверка одной
  командой:

  ```bash
  curl -s -o /dev/null -D - -H "Range: bytes=0-7" \
    http://127.0.0.1:8000/api/guidelines/<guideline_id>/file
  ```

  Ожидается `206` и заголовок `Content-Range`. Проксирование через nginx в compose не покрыто
  автотестами: при `proxy_buffering` диапазоны могут превратиться в `200`, и тогда PDF.js
  скачает файл целиком.
- **Подсветка.** Вердикты пока не приходят, поэтому подсветку никто не запрашивает. Точка входа
  уже есть: `PdfViewer` отдаёт наружу `PdfViewerHandle.goTo({ page, bbox })` — прямое продолжение
  инварианта «клик по источнику → оригинальный PDF на нужной странице». Когда появится
  `GET /api/chunks/{chunk_id}`, координаты `bbox` из ответа нужно передать в `goTo`.

## Структура

```
src/
  api/          клиент к backend и сгенерированные типы
  components/   презентационные компоненты (без запросов)
  hooks/        загрузка данных и побочные эффекты
  lib/          форматирование значений
  pages/        экраны: Library, Viewer, 404
  store/        чистая логика состояния: список, параметры адреса, разбор ошибок
  styles/       токены и базовые стили
```

Правило проекта: компоненты презентационные, запросы и логика — в `api/`, `hooks/`, `store/`.

## Тесты

`npm run test` (Vitest, окружение `node`) покрывает то, что не требует браузера:

- `src/api` — разбор ошибок, query-параметры списка, адрес файла, подписи статусов;
- `src/store` — слияние страниц без дублей, порядок и параметры запросов, параметры адреса;
- `src/lib` — форматирование размера, даты и прогресса;
- дымовые рендеры (`react-dom/server`) — маршруты и строка списка собираются без ошибок.

Что проверяется вручную в браузере: реальная отрисовка PDF, drag&drop, прогресс загрузки и
поведение при недоступном бэкенде.
