# Tasks

## 1. Общие настройки GigaChat

- [x] 1.1 Создать `backend/app/config/gigachat.py` с `GigaChatSettings(BaseEnvSettings)`: `token`,
  `scope`, `base_url`, `verify_ssl_certs`, `ca_bundle_file`, `timeout`, `max_retries` — те же алиасы
  `GIGACHAT_*`, что сейчас в `LLMSettings`, включая валидатор якоря для `ca_bundle_file`. Проверка:
  `python -c "from app.config.gigachat import GigaChatSettings; print(GigaChatSettings().gigachat_token)"`
  не падает, а `python -c "import app.config.llm"` продолжает импортироваться.
- [x] 1.2 Перевести `LLMSettings` на наследование от `GigaChatSettings`, удалив из него перенесённые
  поля и валидатор. Проверка: `pytest tests/test_settings.py -q` — падает только тест уникальности
  алиасов, остальные зелёные; `settings.llm.gigachat_token` и `settings.llm.gigachat_configured`
  работают, `app/clients/llm.py` не изменён (`git diff --stat backend/app/clients/llm.py` пуст).
- [x] 1.3 Уточнить `backend/tests/test_settings.py`: уникальность алиасов проверять внутри домена, а
  повтор между доменами разрешать только для полей, унаследованных от `GigaChatSettings`. Добавить
  проверку, что `EmbeddingSettings.gigachat_token` и `LLMSettings.gigachat_token` читают одну
  переменную. Проверка: `pytest tests/test_settings.py -q` зелёный.

## 2. Настройки эмбеддингов

- [x] 2.1 Переписать `backend/app/config/embedding.py`: наследование от `GigaChatSettings`;
  `model_id` по умолчанию `EmbeddingsGigaR`, `dimension` 2560, `batch_size` 32; удалить `ml_models_dir`,
  `model_path`, `max_seq_length`, `threads`, `device`, `default_threads()` и свойство `model_dir`.
  Проверка: `pytest tests/test_settings.py tests/test_embeddings.py -q` не падает на импорте, а
  `EmbeddingSettings().dimension == 2560`.
- [x] 2.2 Заменить `query_instruction` + `query_prefix` на `query_template` с алиасом
  `EMBEDDING_QUERY_TEMPLATE`, по умолчанию — русская формулировка из рекомендаций Sber для
  retrieval-задач, адаптированная под «пункт протокола → абзац клинрека». Валидатор обязан отклонять
  шаблон без `{text}`. Проверка: новый тест в `tests/test_embeddings.py` — шаблон без `{text}` вызывает
  `ValidationError`, а `EmbeddingSettings().query_template.format(text="x")` содержит `x`.
- [x] 2.3 Обновить `.env.example`: блок Embeddings — `EMBEDDING_MODEL=EmbeddingsGigaR`,
  `EMBEDDING_DIM=2560`, `EMBEDDING_BATCH_SIZE=32`, `EMBEDDING_QUERY_TEMPLATE=...`; удалить
  `ML_MODELS_DIR`, `EMBEDDING_MODEL_PATH`, `EMBEDDING_MAX_SEQ_LENGTH`, `EMBEDDING_THREADS`,
  `EMBEDDING_DEVICE`; в блоке GigaChat отметить, что ключ используется и чатом, и эмбеддингами.
  Проверка: `pytest tests/test_settings.py -q` — тесты соответствия `.env.example` объявленным алиасам
  зелёные.

## 3. Клиент эмбеддингов

- [x] 3.1 Переписать `backend/app/clients/embeddings.py`: `GigaChatEmbedder` с ленивым
  `GigaChat(credentials=..., scope=..., base_url=..., verify_ssl_certs=..., ca_bundle_file=...,
  timeout=..., max_retries=...)`, вызовом `embeddings(texts, model=model_id)`, без `with` и без
  закрытия; `EmbeddingResult(vectors, tokens)`; фабрика `build_embedder(settings)`. Удалить
  `SentenceTransformerEmbedder`, `ensure_model_files`, `_embedding_dimension`, `resolve_device`,
  `REQUIRED_MODEL_FILES`, `WEIGHTS_FILES`. Проверка: `ruff check app/clients/embeddings.py` чист, а
  `grep -r "sentence_transformers\|ensure_model_files\|resolve_device" backend/app` пуст.
- [x] 3.2 Реализовать сверки ответа: раскладка векторов по `item.index`, сверка `response.model` с
  `model_id`, сверка длины каждого вектора с `dimension`. Проверка: тесты в `tests/test_embeddings.py`
  на фейковом клиенте — переставленный `index` даёт векторы в правильном порядке; чужой `model` и
  чужая длина вектора дают `EmbeddingError` с причиной.
- [x] 3.3 Маппинг ошибок: `EmbeddingAuthError` для `AuthenticationError`/`ForbiddenError`;
  `EmbeddingError` для `RateLimitError`, `ServerError`, `httpx.TransportError`, `TimeoutError`,
  `BadRequestError`, `UnprocessableEntityError` и `pydantic.ValidationError`. Пустой или пробельный
  текст обязан отклоняться `EmbeddingError` с позицией в батче и **без** текста фрагмента. Проверка:
  тесты на каждый класс исключения в `tests/test_embeddings.py`; отдельный тест подтверждает, что
  отправленный в клиент `input` не содержит пустых строк и что текст не попал в сообщение ошибки.
- [x] 3.4 Перевести `tests/fakes.py::FakeEmbedder` на `EmbeddingResult` и добавить счётчик
  израсходованных токенов. Проверка: `pytest tests/ -q -k "indexing or chat"` зелёный.

## 4. Сервисы и API

- [x] 4.1 В `backend/app/services/indexing.py` накапливать токены по батчам и писать в журнал итог
  один раз на клинрек: `logger.info` с числом токенов при успехе и с накопленным числом перед сменой
  статуса на `failed`. Текст чанков в журнал не попадает. Проверка: тесты в `tests/test_indexing.py` —
  при успешной индексации в `caplog` есть строка с числом токенов и нет текста чанка; при отказе
  эмбеддера в `caplog` есть накопленное число токенов.
- [x] 4.2 В `backend/app/runtime.py` заменить `SentenceTransformerEmbedder(...)` на
  `build_embedder(self.settings.embedding)`; в `Runtime.close()` поведение не менять. Проверка:
  `pytest tests/ -q` зелёный, `grep -n "SentenceTransformer" -r backend/app` пуст.
- [x] 4.3 В `backend/app/routers/chat.py` перехватывать `EmbeddingError` отдельно от `LLMError` и
  отвечать `502` с причиной, называющей сервис эмбеддингов; добавить `502` в описание `responses` для
  `/ask`. Проверка: новый тест в `tests/test_chat_api.py` — при `EmbeddingError` от эмбеддера ответ
  `502`, тело содержит причину про эмбеддинги, и это не `500` и не ответ «не найдено».

## 5. Зависимости, образ, удаление локальной модели

- [x] 5.1 Убрать из `backend/pyproject.toml` `torch` и `sentence-transformers`, оба индекса
  `pytorch-cu126`/`pytorch-cpu` и секцию `[tool.uv.sources]`; выполнить `uv sync` и подтвердить, что
  `backend/uv.lock` больше не содержит `torch`, `transformers` и pytorch-индексов. Проверка:
  `python -c "import sys; import app.main"` работает, `grep -c "name = \"torch\"" backend/uv.lock` — 0,
  `pytest tests/ -q` зелёный на окружении без PyTorch.
- [x] 5.2 Удалить из `backend/ml_models/` отслеживаемые файлы (`README.md`, `.gitkeep`) и убедиться,
  что `backend/Dockerfile` не ссылается на веса и не требует правок. Папку с весами удаляет владелец:
  она вне git. Проверка:
  `grep -rn "ml_models\|Qwen" backend --include=*.py --include=*.md --include=Dockerfile --include=*.toml`
  пуст.

## 6. Eval без переписывания метрик

- [x] 6.1 В `backend/eval/run.py` заменить импорт и две конструкции `SentenceTransformerEmbedder(...)`
  (основной прогон и `--replay`) на `build_embedder(settings)`. Больше в файле ничего не менять.
  Проверка: `git diff --numstat backend/eval/run.py` показывает не больше 4 изменённых строк;
  `python eval/run.py --check` печатает «no problems».
- [x] 6.2 Подтвердить неприкосновенность эталона и старых метрик на момент правки кода: `eval/cases.toml`,
  `eval/chunk_dump.json`, `eval/chunk_dump.md`, `eval/reports/{a,a2,b3}.json` не изменены. Проверка:
  `git status --porcelain backend/eval` показывает только `run.py`. Позже, по отдельному запросу
  владельца, разметка перепривязана к новым `chunk_id` (см. 8.4); старые отчёты при этом не тронуты —
  подтверждено совпадением SHA256.

## 7. Документация

- [x] 7.1 Обновить `AGENTS.md`: в стеке бэкенда заменить «PyTorch (CPU-сборка) + Sentence-Transformers,
  Qwen3-Embedding-0.6B (1024)» на GigaChat API `EmbeddingsGigaR` (2560), убрать упоминание
  `backend/ml_models/`, отразить, что индексация требует сети и ключа `GIGACHAT_TOKEN`. Проверка:
  `grep -n "Qwen\|PyTorch\|ml_models" AGENTS.md` пуст.
- [x] 7.2 Обновить `backend/README.md`: команды и описание индексации без локальных весов, переменные
  `EMBEDDING_*`, требование ключа GigaChat, стоимость индексации и порядок переиндексации клинреков.
  Проверка: `grep -n "ml_models\|Qwen\|EMBEDDING_DEVICE" backend/README.md` пуст, а упомянутые в README
  команды запускаются как написано.

## 8. Интеграционная проверка

- [x] 8.1 Прогнать `pytest tests/ -q` на чистом окружении и `ruff check .` из `backend/`; исправить
  найденное. Проверка: обе команды завершаются без ошибок.
- [x] 8.2 Проверить живую индексацию: клинрек «Гипертензия» переиндексирован владельцем на новой
  модели. Проверка выполнена: метаданные показывают `ready`, `embedding_model` = `EmbeddingsGigaR`,
  `chunks_total` = 427, а `eval/dump_chunks.py` прочитал все 427 чанков из коллекции
  `guideline_chunks__2560`.
- [x] 8.3 Проверить отказ провайдера: отказ проверен вызовом клиента с неверным `GIGACHAT_TOKEN` —
  GigaChat отвечает `400` от OAuth-сервера, клиент распознаёт это как `EmbeddingAuthError`
  («GigaChat rejected the authorization key for embeddings: 400»); путь `failed` в индексации при
  `EmbeddingError` покрыт тестами `tests/test_indexing.py`. Живая порча библиотеки ради проверки не
  выполнялась.
- [x] 8.4 Снять метрики GigaChat, не перезаписав метрики Qwen. Сначала разметка набора перепривязана к
  текущей загрузке клинрека: `chunk_dump` пересобран, 427 позиций и текстов совпали один в один,
  заменены только `chunk_id` и `guideline_id`. Затем три прогона: `a4` (`--prompt a --baseline a`),
  `a5` (`--prompt a --baseline a4`), `b6` (`--prompt b --baseline b3`). Проверка: появились
  `eval/reports/{a4,a5,b6}.json` с `embedding_model` = `EmbeddingsGigaR`, а SHA256 файлов `a.json`,
  `a2.json`, `b3.json` не изменился; результаты внесены в `EVAL.md`.

## Workflow follow-up

- Не запускать `eval/run.py` с `--name a|a2|b3`: это перезапишет метрики Qwen.
- Архивация изменения — после того, как метрики GigaChat сняты и просмотрены.
