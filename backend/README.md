# Backend (Smart Doctor API)

FastAPI-сервис проверки врачебных протоколов. См. корневой [README](../README.md) и [AGENTS.md](../AGENTS.md).
Контракт эндпоинтов — [API.md](API.md).

## Запуск

Точка входа одна и та же локально и в контейнере: `python app/__main__.py`.

```bash
cd backend
uv sync                        # поставить зависимости в .venv
python app/__main__.py         # http://127.0.0.1:8000, /docs — Swagger
```

PostgreSQL и Qdrant для текущих эндпоинтов не нужны — соединения не открываются.

Параметры задаются переменными окружения (`backend/.env`, затем корневой `.env`, см. [`.env.example`](../.env.example)):

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `HOST` | `127.0.0.1` (в контейнере `0.0.0.0`) | адрес bind |
| `PORT` | `8000` | порт |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `STORAGE_DIR` | `storage` | каталог PDF и метаданных |
| `MAX_UPLOAD_SIZE_MB` | `50` | лимит размера загружаемого PDF |

Проверка:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/guidelines -F "file=@klinrek.pdf" -F "title=Клинрек"
```

Автоперезапуска нет: после правок кода сервер перезапускается вручную.

## Хранилище

PDF и метаданные клинреков лежат в `backend/storage/guidelines/<guideline_id>/`
(`original.pdf` + `meta.json`). Каталог создаётся при первом запросе, в git не попадает.

## Команды

| Задача | Команда |
|---|---|
| Запуск | `python app/__main__.py` |
| Тесты | `uv run pytest -v` |
| Линт | `uv run ruff check .` |
| Добавить зависимость | `uv add <package>` |
