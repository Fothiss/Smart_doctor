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
| `GIGACHAT_TOKEN` | — | ключ авторизации GigaChat: нужен и чату, и эмбеддингам |
| `EMBEDDING_MODEL` | `EmbeddingsGigaR` | имя модели эмбеддингов в API |
| `EMBEDDING_DIM` | `2560` | размерность вектора: сверяется с коллекцией Qdrant |
| `EMBEDDING_BATCH_SIZE` | `32` | сколько чанков уходит в сервис за один запрос |
| `EMBEDDING_QUERY_TEMPLATE` | русская инструкция | шаблон запроса, обязан содержать `{text}` |

Проверка:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/guidelines -F "file=@klinrek.pdf" -F "title=Клинрек"
curl http://127.0.0.1:8000/api/guidelines/<guideline_id>
```

Автоперезапуска нет: после правок кода сервер перезапускается вручную.

## Индексация

После загрузки PDF клинрек сразу уходит в индексацию: текст извлекается постранично, режется на
чанки по абзацам и секциям, векторизуется сервисом эмбеддингов GigaChat и складывается в Qdrant.
Статусы: `uploaded → processing → ready | failed`, ход виден в `chunks_indexed`/`chunks_total`,
причина отказа — в `error`. Повторный запуск — `POST /api/guidelines/{guideline_id}/index`.

Индексация требует сети и ключа `GIGACHAT_TOKEN`: векторы считает модель `EmbeddingsGigaR`
(2560 измерений, контекст 4096 токенов). Замер: ~30 мс на чанк при порции 32, ~10 ₽ за
220-страничный клинрек. Число израсходованных токенов пишется в журнал после каждого прогона,
включая упавшие. Без сети индексация уходит в `failed` с причиной, называющей сервис эмбеддингов.

Векторное хранилище открывается лениво, поэтому загрузка, список и просмотр PDF работают и без
настроенного GigaChat.

Смена модели эмбеддингов меняет пространство векторов: размерность входит в имя коллекции
(`guideline_chunks__2560`), поэтому после смены модели клинреки нужно переиндексировать по одному.

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
