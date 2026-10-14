# Proposal

## Why

На бэкенде реализованы и покрыты тестами четыре эндпоинта для работы с PDF клинреков (`POST /api/guidelines`,
`GET /api/guidelines`, `GET /api/guidelines/{guideline_id}`, `GET /api/guidelines/{guideline_id}/file`), но
проверить их из браузера нельзя: во `frontend/` лежат только `Dockerfile`, `nginx.conf` и `.dockerignore` —
ни `package.json`, ни `src/`, ни точки сборки. Первый шаг README («Библиотека клинреков») недоступен
пользователю, а контракт API не проверен ни одним реальным клиентом.

## What Changes

- Инициализируется SPA-приложение во `frontend/`: Vite + React + TypeScript (strict), ESLint/Prettier,
  `npm run dev`, `npm run build`, `npm run lint`.
- Появляется типизированный клиент к API (`src/api/`) с генерацией типов из `openapi.json` и единой
  обработкой ошибок `{"detail": ...}` — строки для 400/404/413 и объекта для 409.
- Экран Library (`/library`): список клинреков с фильтром по статусу и постраничной догрузкой,
  загрузка PDF с прогрессом, разбор ошибок 400/409/413 — при 409 показывается ссылка на уже
  загруженный клинрек. Состояния загрузки, пустоты и ошибки разведены явно.
- Экран просмотра PDF (`/library/:guidelineId/view`): рендер оригинала через PDF.js с навигацией по
  страницам и зумом, шапка с метаданными клинрека. Подсветка чанков не входит в изменение, но вьюер
  получает программный интерфейс перехода к странице и прямоугольнику — чтобы будущие вердикты
  подключались без переписывания.
- Загрузка PDF идёт через `/api/guidelines/{id}/file` с использованием `Range`; PDF.js worker
  собирается Vite и проверяется не только в dev, но и в собранном образе.
- Бэкенд не изменяется: ни эндпоинты, ни схемы, ни CORS. В dev-режиме CORS обходится проксированием
  `/api` на Vite; в проде — существующим `location /api/` в `nginx.conf`.

## Capabilities

### New Capabilities

- `guideline-library`: загрузка PDF клинрека, список загруженных клинреков с их статусом и метаданными,
  обработка отказов загрузки (пустой файл, не PDF, превышение размера, дубликат по содержимому).
- `guideline-viewer`: просмотр оригинального PDF клинрека с навигацией по страницам, зумом и
  возможностью адресно открыть страницу и область документа.

### Modified Capabilities

Нет. `openspec/specs/` пуст, поведение существующих эндпоинтов не меняется — изменение добавляет
потребителя API, а не новые серверные требования.

## Impact

- **Новый код:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig*.json`,
  `frontend/eslint.config.js`, `frontend/index.html`, `frontend/src/**` (`api/`, `pages/`, `components/`,
  `hooks/`, `styles/`), `frontend/README.md`.
- **Затрагиваемое:** `frontend/Dockerfile` (уже ожидает `package.json`/`package-lock.json` и `npm run build`),
  `frontend/nginx.conf` (проверка проксирования `/api/` и `Range`), `docker-compose.yml` (сервис `frontend`
  начинает собираться по-настоящему), `.gitignore` (артефакты Node).
- **Зависимости:** `react`, `react-dom`, `react-router-dom`, `pdfjs-dist`; dev: `vite`, `typescript`,
  `eslint`, `prettier`, `vitest`, `openapi-typescript`.
- **Не входит в изменение:** ingestion-пайплайн (статусы `processing`/`ready`/`failed` остаются
  недостижимыми), подсветка чанков, экраны протокола, отчёта, чата и истории, обратная связь по вердиктам.
