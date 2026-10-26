# AGENTS.md

## Role
You are a full-stack developer for this project. Reply briefly, focus on technical substance.

## Communication
- Always respond in Russian.
- Be concise. No filler words. No greetings, no closing remarks.
- Code examples over long explanations.

## Project Overview
Smart Doctor — AI-ассистент для проверки врачебных протоколов на соответствие клиническим рекомендациям.
Single-user MVP. Каждый вердикт системы обязан ссылаться на конкретный чанк клинрека.

Стек: FastAPI + React SPA + PostgreSQL + Qdrant + LLM через клиент (GigaChat или DeepSeek). Всё в Docker Compose.

## Repository Layout

### Backend (`backend/`)
Layered architecture.
- `app/routers/` — API layer. One router per feature.
- `app/services/` — business logic. LLM calls, RAG, parsing, vector DB queries live here.
- `app/services/prompts/` — промпты и схемы structured output.
- `app/clients/` — клиенты к внешним системам (LLM, embeddings).
- `app/config/` — settings from env vars. Import `settings` singleton.
- `app/schemas/` — Pydantic request/response models.

**Rule:** Routers parse request and call services. Logic lives in services.

### Frontend (`frontend/`)
SPA + PDF viewer.
- `src/pages/` — экраны (Library, Protocol form, Report, Chat, History).
- `src/components/` — переиспользуемые компоненты.
- `src/api/` — клиент к backend.
- `src/store/` — состояние приложения.

**Rule:** Компоненты — презентационные. Логика и запросы — в хуках/сторе/API-клиенте.

### Infra
- `docker-compose.yml` — оркестрация всех сервисов.
- `.env` — в корне проекта.

## Tech Stack

### Backend
- Python 3.12, `uv` package manager
- FastAPI 0.142 + Uvicorn (port 8000)
- PostgreSQL — метаданные, история, feedback (в текущих эндпоинтах не используется)
- Qdrant — векторная БД (чанки клинреков + эмбеддинги); по умолчанию локальный режим
  `qdrant-client` в `backend/storage/qdrant`, сервер — через `QDRANT_MODE=server`
- PyTorch (CPU-сборка) + Sentence-Transformers — локальные эмбеддинги на CPU
- Модель эмбеддингов — `Qwen3-Embedding-0.6B` (1024 измерения), файлы лежат в
  `backend/ml_models/` и в git не попадают: см. [`backend/ml_models/README.md`](backend/ml_models/README.md)
- Ingestion: `pdfplumber` → абзацы → чанки → эмбеддинги → Qdrant; сервисы в
  `app/services/`, клиенты в `app/clients/`
- LLM-клиент: GigaChat или DeepSeek (выбор через env, единый интерфейс в `app/clients/`)

### Frontend
- TypeScript, React + Vite
- Стилизация — Tailwind CSS v4 (плагин `@tailwindcss/vite`); компоненты — shadcn/ui поверх Radix
  (Dialog, Combobox, Toast, Tooltip берутся из UI-kit, а не пишутся руками)
- Токены оформления — единственный источник в `src/styles/tokens.css` (`@theme`), из них Tailwind
  строит утилиты; произвольные значения цветов в разметке и «свои» палитры на экранах запрещены
- Шрифты лежат в `frontend/public/fonts` (Inter/JetBrains Mono, кириллица); внешних CDN нет,
  перегенерировать — `node scripts/fetch-fonts.mjs`
- Новые экраны собираются сразу на UI-kit; CSS-модули остаются только в ещё не переведённых экранах,
  в одном компоненте оба подхода не смешиваются
- PDF.js — просмотр клинреков с подсветкой чанков

### Infra
- Docker Compose
- Nginx (опционально) — reverse proxy

## Commands

Точка входа одна и та же локально и в контейнере: `python app/__main__.py` из `backend/` (тот же
`CMD` в `backend/Dockerfile`). Автоперезапуска нет: после правок сервер перезапускается вручную.
Команды для человека — в [`backend/README.md`](backend/README.md).

### Backend
- Run dev: `python app/__main__.py` (из `backend/`) — http://127.0.0.1:8000, `/docs` — Swagger
- Tests: `uv run pytest -v`
- Lint: `uv run ruff check .`
- Add dep: `uv add <package>`

### Frontend
- Run dev: `npm run dev` — http://localhost:5173 (Vite слушает `localhost`; на этой машине это IPv6,
  поэтому `127.0.0.1:5173` не отвечает), `/api` проксируется на `127.0.0.1:8000`
- Build: `npm run build`
- Lint: `npm run lint`
- Tests: `npm run test`
- Типы из контракта: `npm run gen:api`

### Infra
- Нужен запущенный Docker Desktop: без него `docker compose` падает на подключении к демону.
- Up: `docker compose up -d`
- Logs: `docker compose logs -f <service>`
- Rebuild: `docker compose up -d --build <service>`

### Подстановки для окружения агента

Windows + песочница DSH: `python` в `PATH` — заглушка Microsoft Store, `uv` в `PATH` нет (он
установлен только в `backend/.venv`), а `.ps1` без подписи не запускаются при `ExecutionPolicy
AllSigned`. Поэтому зови интерпретатор и инструменты явными путями, а вместо `npm` — `npm.cmd`:

| Канон | В окружении агента |
|---|---|
| `python app/__main__.py` (из `backend/`) | `backend\.venv\Scripts\python.exe backend\app\__main__.py` (из корня репозитория) |
| `uv run pytest -v` | `cd backend; .\.venv\Scripts\python.exe -m pytest -v` |
| `uv run ruff check .` | `cd backend; .\.venv\Scripts\python.exe -m ruff check .` |
| `uv add <package>` | `cd backend; .\.venv\Scripts\uv.exe add <package>` |
| `npm run <script>` (из `frontend/`) | `cd frontend; npm.cmd run <script>` |

Отдельно: `vite`/`vitest` при загрузке конфигурации выполняют `exec("net use")` для Windows-realpath и
в песочнице падают с `spawn EPERM` — эти команды требуют полного доступа к системе. Кэш npm вне
воркспейса тоже недоступен: используй `--cache .tmp-npm-cache` (каталог уже в `.gitignore`).

Форма `python -m app` тоже работает, но только venv-питоном и только из `backend/`: из корня
репозитория она падает с `No module named app`.

## Code Style — Zen of Python
Apply these when writing or reviewing code:
- Beautiful is better than ugly.
- Explicit is better than implicit.
- Simple is better than complex.
- Readability counts.
- Errors should never pass silently.

**Rules:**
- Type hints required (Python) / strict TypeScript.
- Use `uv add` for Python deps, `npm install` for JS deps.
- Log messages in English, comments/docstrings in Russian.
- Never log patient text or secrets.
- Structured output от LLM — всегда валидируется Pydantic-схемой.
- Вердикт без `chunk_id` не выдаётся — это инвариант системы.
- LLM вызывается только через `app/clients/`, не напрямую из сервисов.

## Architecture Assessment (Before Any Change)
Before modifying code, evaluate architecture fit:

1. **Does this change fit current architecture?** If yes, proceed.
2. **If no, can architecture adapt slightly?** Small refactor OK. State what and why.
3. **If large architectural change needed,** stop and ask user first.

**Do not** silently reshape architecture for one feature. State assessment, propose minimal change, then implement.

## Domain Invariants
- Каждый вердикт обязан ссылаться на существующий чанк клинрека.
- `confidence < 0.6` → пункт уходит в «Требует внимания».
- Клик по источнику → оригинальный PDF на нужной странице с подсветкой.
- Версионирование клинреков: старые отчёты привязаны к своей версии документа.
- Промпты и схемы structured output живут в `app/services/prompts/`, не inline.
- Смена LLM-провайдера не должна требовать изменений в сервисах — только в `app/clients/`.