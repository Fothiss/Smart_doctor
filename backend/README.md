# Backend (Smart Doctor API)

FastAPI-сервис проверки врачебных протоколов. См. корневой [README](../README.md) и [AGENTS.md](../AGENTS.md).
Контракт эндпоинтов — [API.md](API.md).

## Запуск

Точка входа одна и та же локально и в контейнере: `python app/__main__.py`.

```bash
cd backend
uv sync                            # поставить зависимости в .venv
uv run python app/__main__.py      # http://127.0.0.1:8000, /docs — Swagger
```

`uv run` сам подставляет интерпретатор из `.venv`. Без него нужен активированный venv: `uv sync`
создаёт `.venv`, но `python` из `PATH` остаётся системным и упадёт на `import fastapi`.

PostgreSQL текущим эндпоинтам не нужен: соединение не открывается. Qdrant нужен только индексации —
по умолчанию он локальный (`QDRANT_MODE=local`) и кладёт данные в `backend/storage/qdrant`, поэтому
контейнеры для разработки не требуются.

Параметры задаются переменными окружения (`backend/.env`, затем корневой `.env`, см. [`.env.example`](../.env.example)):

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `HOST` | `127.0.0.1` (в контейнере `0.0.0.0`) | адрес bind |
| `PORT` | `8000` | порт |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `STORAGE_DIR` | `storage` | каталог PDF и метаданных |
| `MAX_UPLOAD_SIZE_MB` | `50` | лимит размера загружаемого PDF |
| `CHUNK_TARGET_CHARS` / `CHUNK_MIN_CHARS` / `CHUNK_MAX_CHARS` | `800` / `300` / `1500` | размеры чанка |
| `CHUNK_OVERLAP_CHARS` | `150` | перекрытие при разрыве абзаца |
| `QDRANT_MODE` | `local` | `local` — хранилище в каталоге, `server` — сервер по `QDRANT_URL` |
| `QDRANT_LOCAL_PATH` | `storage/qdrant` | каталог локального хранилища |
| `QDRANT_COLLECTION` | `guideline_chunks` | база имени коллекции: размерность дописывается кодом |
| `QDRANT_URL` | `http://localhost:6333` | адрес сервера Qdrant для режима `server` |
| `ML_MODELS_DIR` | `ml_models` | каталог с папками моделей эмбеддингов |
| `EMBEDDING_MODEL_PATH` | `Qwen3-Embedding-0.6B` | папка модели внутри `ML_MODELS_DIR` |
| `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | идентификатор модели для метаданных |
| `EMBEDDING_DIM` | `1024` | размерность вектора |
| `EMBEDDING_MAX_SEQ_LENGTH` | `512` | предел длины входа |
| `EMBEDDING_BATCH_SIZE` | `8` | сколько чанков кодируется за проход |
| `EMBEDDING_DEVICE` | `auto` | `auto` — видеокарта, если сборка PyTorch её видит; `cpu` — всегда процессор |
| `EMBEDDING_THREADS` | все ядра минус одно | потоки инференса на CPU |
| `EMBEDDING_QUERY_INSTRUCTION` | английская инструкция | префикс запроса: документы кодируются без него |

Проверка:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/guidelines -F "file=@klinrek.pdf" -F "title=Клинрек"
curl http://127.0.0.1:8000/api/guidelines/<guideline_id>
```

Автоперезапуска нет: после правок кода сервер перезапускается вручную.

## Индексация

После загрузки PDF клинрек сразу уходит в индексацию: текст извлекается постранично, режется на
чанки по абзацам и секциям, векторизуется локальной моделью и складывается в Qdrant. Статусы:
`uploaded → processing → ready | failed`, ход виден в `chunks_indexed`/`chunks_total`, причина отказа —
в `error`. Повторный запуск — `POST /api/guidelines/{guideline_id}/index`.

Индексация идёт минутами: 220-страничный клинрек — это сотни чанков и десятки секунд только на
извлечение текста. Векторное хранилище открывается лениво, поэтому загрузка, список и просмотр PDF
работают и без модели в `ml_models`.

## Хранилище

PDF и метаданные клинреков лежат в `backend/storage/guidelines/<guideline_id>/`
(`original.pdf` + `meta.json`). Каталог создаётся при первом запросе, в git не попадает.
Векторы чанков — в `backend/storage/qdrant` (локальный режим Qdrant), тоже вне git.

## Команды

| Задача | Команда |
|---|---|
| Запуск | `uv run python app/__main__.py` |
| Тесты | `uv run pytest -v` |
| Линт | `uv run ruff check .` |
| Добавить зависимость | `uv add <package>` |
