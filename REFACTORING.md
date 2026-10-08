# Рефакторинг бэкенда

Выжимка изменений по итогам ревью: два блокера и конфигурация. Код — `backend/`, ничего не перезапускалось.

## 1. Настройки: `app/config/` разложен по доменам

- `base_settings.py` — базовое чтение окружения (`BaseEnvSettings`) и **собственные настройки бэкенда** (`BackendSettings`: имя/версия, `HOST`, `PORT`, `LOG_LEVEL`, `STORAGE_DIR`, `MAX_UPLOAD_SIZE_MB`).
- `database.py` — `DatabaseSettings` (`DATABASE_URL`, `QDRANT_URL`) и `DatabaseNotConfiguredError`.
- `llm.py` — `LLMSettings` (провайдер, ключи, `EMBEDDING_MODEL`) и `LLMProvider(StrEnum)`.
- `settings.py` — агрегат `Settings(backend, database, llm)` и `get_settings()` под `lru_cache`.
- `app_settings.py` удалён: его поля переехали в `base_settings.py`.
- **Каждое поле — `Field(default=..., validation_alias="ENV_NAME", description=...)`**: имя переменной окружения объявлено явно, дефолт явный, алиасы уникальны и в верхнем регистре.
- `populate_by_name=True` — настройки собираются и аргументами по имени поля, а не только переменными окружения (нужно тестам и DI).
- Пути `.env` считаются от файла настроек, а не от текущего каталога: корневой `.env`, затем `backend/.env` (приоритет у последнего).
- Относительный `STORAGE_DIR` якорится к `backend/` (раньше зависел от каталога запуска: из другого места получался `C:\Users\<user>\storage`).
- `HOST` по умолчанию `127.0.0.1` вместо `0.0.0.0` — совпадает с README и `.env.example`.
- `DATABASE_URL` без рабочего дефолта с паролем: DSN в коде не хранится, обращение через `sqlalchemy_url` падает с явной ошибкой.
- Ключи LLM — `SecretStr`: не попадают в `repr` и логи. Неизвестный `LLM_PROVIDER` роняет старт, а не откатывается молча.

## 2. Сервис клинреков отвязан от FastAPI (блокер)

- `app/services/guidelines.py` больше не импортирует `fastapi`/`UploadFile`: на вход `AsyncIterator[bytes]`, на выход доменный `Guideline`.
- Лимит размера приходит в конструктор (`max_upload_size_bytes`), а не берётся из глобального `settings`.
- Чтение загрузки порциями (1 МБ) переехало в API-слой: `_read_chunks` в роутере.
- `mkdir` убран из конструктора — каталог создаётся при первой загрузке, без побочных эффектов при импорте.
- `safe_filename()` отбрасывает путь по любому разделителю: одинаково локально и в Linux-контейнере.

## 3. DI и точки входа

- `get_guideline_service` — провайдер зависимостей API-слоя, собирает сервис из `Settings`.
- `/health` получает настройки через `Depends(get_settings)`.
- `create_app(settings=None)` — настройки подменяемы в тестах.
- Глобального объекта `settings` больше нет: конфигурация приходит аргументом или зависимостью.

## 4. Тесты и тулинг (блокер)

- `pyproject.toml`: `[dependency-groups] dev` (pytest, pytest-asyncio, httpx, ruff), `[tool.pytest.ini_options]` (`testpaths`, `pythonpath`, `asyncio_mode=auto`), `[tool.ruff]` (line-length 100, py312, `E/F/I/UP/B/SIM/RUF`, `RUF001-003` отключены — код на русском).
- `backend/tests/`: `conftest.py`, `test_guidelines_service.py`, `test_guidelines_api.py`, `test_settings.py` — **53 теста**: валидация файла, лимит размера, дедупликация по sha256, очистка мусора при ошибке, чтение/список/сортировка/пагинация, коды 400/404/409/413, Range-запросы PDF, алиасы и якоря настроек, `SecretStr`.
- Команды из `AGENTS.md` стали рабочими: `uv run pytest -v`, `uv run ruff check .`.

## 5. Окружение и документация

- `.env.example`: добавлен `MAX_UPLOAD_SIZE_MB`, описаны приоритет `.env` и поведение без `DATABASE_URL`.
- Тест сверяет `.env.example` с объявленными алиасами в обе стороны: опечатка в имени переменной больше не превращается молча в дефолт.
- `backend/README.md` не обновлён: в таблице переменных нет `APP_NAME`, `APP_VERSION`, `DATABASE_URL`, `QDRANT_URL`, `LLM_*`, `EMBEDDING_MODEL` — нужно дописать.

## Проверка

- `ruff check .` — `All checks passed`.
- `pytest`: набор собирается (53 теста). Полный прогон **не подтверждён**: песочница DSH не даёт процессу доступ к каталогам, которые pytest создаёт с режимом 0700 (`tmp_path`, `basetemp`) — `WinError 5`; эскалация прав для ремонта прав Windows отклонена. Тесты настроек без `tmp_path` проходят (11 passed).
- На обычной машине: `cd backend && uv run pytest -v`.

## Осталось из ревью (в правки не входило)

- Блокирующий I/O в `async def` обработчиках `list`/`get`/`file` — объявить `def` (threadpool) или `anyio.to_thread`.
- `limit` без верхней границы (`Query(le=...)`), пагинация выполняется после чтения всех манифестов.
- Гонка дедупликации: `sha256` проверяется после записи, без блокировки.
- `except BaseException` в `create` ловит отмену и `KeyboardInterrupt`.
- `get_pdf` берёт путь от `guideline.guideline_id`, а манифест читается по каталогу из URL.
- `meta.json` пишется неатомарно (нужен `tmp` + `os.replace`).
- `Guideline.version` всегда `1` — версионирование клинреков не реализовано, хотя описано в `API.md`.
- `extra="ignore"` сохранён осознанно: корневой `.env` общий с Docker Compose (`POSTGRES_*`, `BACKEND_PORT`, `FRONTEND_PORT`).

## Артефакты песочницы

Эти каталоги созданы попытками прогона тестов и не удаляются из-под песочницы (отказано в доступе) — удалить вручную:

- `backend/pytest-tmp/`
- `backend/pytest-of-highs/`
- `tmp_pytest/`
