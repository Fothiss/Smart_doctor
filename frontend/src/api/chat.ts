/** Клиент чата по клинрекам; типы берутся из сгенерированной схемы. */

import { postJson } from './client'
import type { components } from './schema'

export type ChatAskRequest = components['schemas']['ChatAskRequest']
export type ChatAnswer = components['schemas']['ChatAnswer']
export type ChatCitation = components['schemas']['Citation']
export type ChatMessage = components['schemas']['ChatMessage']
export type ChatGuidelineRef = components['schemas']['ChatGuidelineRef']
export type ChatStatus = components['schemas']['ChatStatus']

/** Адрес вопроса по выбранным клинрекам. */
export const CHAT_ASK_PATH = '/api/chat/ask'

/**
 * Задать вопрос по выбранным клинрекам.
 *
 * Ответ приходит целиком: статус `answered` с подтверждёнными ссылками либо `not_found`.
 * Отказ по существу вопроса — не ошибка транспорта, поэтому разбирается вызывающим.
 */
export async function askChat(body: ChatAskRequest, init?: RequestInit): Promise<ChatAnswer> {
  return postJson<ChatAnswer>(CHAT_ASK_PATH, body, init)
}
