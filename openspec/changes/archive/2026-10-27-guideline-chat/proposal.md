# Proposal

## Why

Сейчас врач может загрузить клинрек, посмотреть оригинал PDF и проверить корректность формы протокола. Ответить на
вопрос «а что сказано про дозы при диабете?» ему нечем: чанки и эмбеддинги в Qdrant уже лежат, но поиска по ним нет,
LLM-клиента в проекте тоже нет.

Чат по выбранным клинрекам — первый потребитель retrieval и первый вызов LLM. Он даёт немедленную пользу врачу и
одновременно закрывает инфраструктуру (`search()`, клиент LLM, промпты, проверка цитат), без которой не сделать
проверку протокола. Поэтому делаем его первым.

## What Changes

- Новый экран «Чат»: мультивыбор загруженных клинреков (только `ready`), лента вопросов и ответов, ответ со ссылками на
  фрагменты.
- Новый эндпоинт `POST /api/chat/ask`: вопрос по выбранным документам, ответ строится только по их фрагментам.
- Клиент LLM на `langchain-gigachat` (`GigaChat`, `credentials` = ключ из `GIGACHAT_TOKEN`), structured output через
  `with_structured_output`.
- Переписывание запроса перед поиском (`rewrite` всегда, без гейта): короткое уточнение вроде «а если ещё диабет?»
  превращается в самодостаточный тезис; результат проверяется на потерю условий и при провале заменяется склейкой с
  прошлым вопросом.
- Поиск по векторному хранилищу с жёстким фильтром по идентификаторам выбранных клинреков.
- Каждый пункт ответа обязан ссылаться на фрагмент; ссылка, не подтверждённая текстом чанка, отбрасывается; ответ без
  подтверждённых ссылок не выдаётся.
- Переход из ответа в просмотрщик на нужной странице с подсветкой — существующий механизм `?chunk=`, без изменений в
  просмотрщике.
- **BREAKING** нет: существующие эндпоинты, экраны и спеки не меняются.

История диалога не хранится на сервере: каждая реплика — отдельный запрос с окном из последних сообщений.
Агент с тулзами, reranker, стриминг и оценка качества (golden set) в этот change не входят.

## Capabilities

### New Capabilities

- `guideline-chat`: вопрос врача по выбранным клинрекам, ответ со ссылками на фрагменты этих документов, отказ при
  отсутствии подтверждённых ссылок.

### Modified Capabilities

Нет.

## Impact

- Backend: `app/config/llm.py` (переменные GigaChat, параметры поиска), `app/clients/llm.py` (новый), `app/clients/vector_store.py`
  (`search()`), `app/services/retrieval.py`, `app/services/query_rewrite.py`, `app/services/chat.py`, `app/services/prompts/`
  (новая папка), `app/schemas/chat.py`, `app/routers/chat.py`, `app/runtime.py`, `app/main.py`.
- Зависимости: `langchain-gigachat` (тянет `gigachat`, `langchain-core`).
- Контракт: `openapi.json` и `frontend/src/api/schema.d.ts` перегенерируются; `POST /api/chat/ask` — новый эндпоинт.
- Frontend: `src/api/chat.ts`, `src/pages/ChatPage.tsx`, `src/store/chat.ts`, `src/components/ui/MultiCombobox.tsx`,
  маршрут `/chat` и пункт меню.
- Конфигурация: `.env.example` — `GIGACHAT_TOKEN`, `GIGACHAT_MODEL`, `GIGACHAT_REWRITE_MODEL`, `GIGACHAT_VERIFY_SSL_CERTS`,
  `CHAT_TOP_K`, `CHAT_MAX_CONTEXT_CHARS`, `CHAT_HISTORY_WINDOW`; сверка с `test_settings.py` обязательна.
- Внешние системы: GigaChat API (`https://api.giga.chat/v1`), локальный Qdrant и модель эмбеддингов.
- Спеки `guideline-library`, `guideline-viewer`, `guideline-ingestion`, `protocol-form` не меняются.
