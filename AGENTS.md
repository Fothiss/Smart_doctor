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
Layered architecture, no repository layer.
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
- FastAPI 0.115 + Uvicorn (port 8000)
- PostgreSQL — метаданные, история, feedback
- Qdrant — векторная БД (чанки клинреков + embeddings)
- PyTorch 2.5.1, Sentence-Transformers — локальные embeddings на CPU
- LLM-клиент: GigaChat или DeepSeek (выбор через env, единый интерфейс в `app/clients/`)

### Frontend
- TypeScript, React + Vite
- PDF.js — просмотр клинреков с подсветкой чанков
- Минимальный UI-kit, без тяжёлых библиотек

### Infra
- Docker Compose
- Nginx (опционально) — reverse proxy

## Commands

### Backend
- Run dev: `python -m app`
- Tests: `uv run pytest -v`
- Lint: `uv run ruff check .`
- Add dep: `uv add <package>`

### Frontend
- Run dev: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`

### Infra
- Up: `docker compose up -d`
- Logs: `docker compose logs -f <service>`
- Rebuild: `docker compose up -d --build <service>`

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