/**
 * Тексты отказов валидации черновика протокола.
 *
 * Коды ответов важнее формулировки сервера: `400` уже называет поле, а `404` и `409`
 * объясняют, что делать дальше.
 */

import { ApiError, describeError } from '../api/client'

/** Читаемое сообщение для отказа валидации. */
export function describeValidationError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400) {
      return `Форма отклонена: ${error.message}`
    }
    if (error.status === 404) {
      return 'Клинрек не найден — возможно, его удалили. Выберите другой клинрек.'
    }
    if (error.status === 409) {
      return 'Клинрек ещё не готов к проверке: дождитесь окончания индексации.'
    }
  }
  return describeError(error)
}
