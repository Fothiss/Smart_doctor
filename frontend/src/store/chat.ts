/**
 * Состояние чата: выбранные документы, лента и разбор ответа.
 *
 * Чистые функции без React: экран остаётся презентационным, а правила — какие документы
 * можно выбрать, сколько сообщений уходит в окно истории, как собрать запрос — проверяются
 * тестами без браузера.
 */

import type { ChatAnswer, ChatAskRequest, ChatCitation, ChatMessage } from '../api/chat'

/** Параметр адреса со списком выбранных клинреков. */
export const DOCS_PARAM = 'docs'

/** Сколько последних сообщений влияет на поисковый запрос: столько же, сколько на сервере. */
export const HISTORY_WINDOW = 4

/** Столько документов можно выбрать в одном вопросе. */
export const MAX_DOCS = 5

/** Одна пара «вопрос — ответ» в ленте. */
export type ChatEntry = {
  question: string
  answer: ChatAnswer
}

/** Прочитать выбранные документы из адреса, отбросив пустые значения. */
export function readSelectedDocs(params: URLSearchParams): string[] {
  const raw = params.get(DOCS_PARAM)
  if (raw === null) {
    return []
  }
  const unique = new Set(
    raw
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value !== ''),
  )
  return [...unique]
}

/** Записать выбранные документы в адрес: пустой выбор убирает параметр. */
export function writeSelectedDocs(params: URLSearchParams, ids: readonly string[]): URLSearchParams {
  const next = new URLSearchParams(params)
  if (ids.length === 0) {
    next.delete(DOCS_PARAM)
  } else {
    next.set(DOCS_PARAM, ids.join(','))
  }
  return next
}

/** Можно ли отправить вопрос: нужен непустой текст и хотя бы один документ. */
export function canAsk(question: string, ids: readonly string[]): boolean {
  return question.trim() !== '' && ids.length > 0
}

/** Подтверждённые ссылки ответа; пустой список, если сервер их не прислал. */
export function citationsOf(answer: ChatAnswer): ChatCitation[] {
  return answer.citations ?? []
}

/** Документы, по которым шёл поиск: подпись для строки прозрачности. */
export function searchedTitles(answer: ChatAnswer): string {
  return (answer.searched_guidelines ?? []).map((item) => item.title).join(', ')
}

/** Проверить форму ответа: сервер мог вернуть не тот статус. */
export function isAnswered(answer: ChatAnswer): boolean {
  return (
    answer.status === 'answered' &&
    typeof answer.answer === 'string' &&
    answer.answer !== '' &&
    citationsOf(answer).length > 0
  )
}

/**
 * Собрать окно истории из ленты.
 *
 * Каждая реплика даёт два сообщения, поэтому окно в четыре сообщения — это две последние
 * пары. Прошлые ответы уходят только текстом: их цитаты сервер не использует.
 */
export function buildHistory(
  entries: readonly ChatEntry[],
  window: number = HISTORY_WINDOW,
): ChatMessage[] {
  const messages: ChatMessage[] = []
  for (const entry of entries) {
    messages.push({ role: 'user', text: entry.question })
    if (typeof entry.answer.answer === 'string' && entry.answer.answer !== '') {
      messages.push({
        role: 'assistant',
        text: entry.answer.answer,
        citations: citationsOf(entry.answer).map((citation) => ({ chunk_id: citation.chunk_id })),
      })
    }
  }
  return window > 0 ? messages.slice(-window) : []
}

/** Собрать тело запроса к серверу. */
export function askRequest(
  ids: readonly string[],
  question: string,
  entries: readonly ChatEntry[],
): ChatAskRequest {
  return {
    guideline_ids: [...ids],
    question: question.trim(),
    history: buildHistory(entries),
  }
}

/** Адрес фрагмента в просмотрщике: открывается на нужной странице с подсветкой. */
export function citationHref(guidelineId: string, chunkId: string): string {
  const base = `/library/${encodeURIComponent(guidelineId)}/view`
  return `${base}?chunk=${encodeURIComponent(chunkId)}`
}

/** Подтверждённые ссылки ответа по их номерам: по номеру из текста находим адрес. */
export function citationIndex(
  answer: ChatAnswer,
): Map<number, { guideline_id: string; chunk_id: string }> {
  return new Map(
    citationsOf(answer).map((citation) => [
      citation.n,
      { guideline_id: citation.guideline_id, chunk_id: citation.chunk_id },
    ]),
  )
}

/**
 * Сквозные номера для показа: номер в контексте модели → номер в ответе.
 *
 * Модель нумерует фрагменты всего контекста (восемь штук), а ссылается на два-три.
 * Показывать «[4] и [5]» без 1–3 — значит заставлять врача искать недостающие номера,
 * поэтому в ответе ссылки нумеруются подряд, в порядке появления.
 */
export function displayLabels(answer: ChatAnswer): Map<number, number> {
  return new Map(citationsOf(answer).map((citation, index) => [citation.n, index + 1]))
}
