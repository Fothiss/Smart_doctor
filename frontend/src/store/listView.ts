/**
 * Выбор состояния экрана библиотеки.
 *
 * Состояния разведены явно: пустое хранилище не должно читаться как сбой, а ошибка — как
 * пустой список. Чистая функция, поэтому проверяется тестом без браузера.
 */

import type { GuidelineStatus } from '../api/guidelines'

export type ListView =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty'; filtered: boolean }
  | { kind: 'list' }

export type ListViewInput = {
  isLoading: boolean
  error: string | null
  count: number
  /** Выбранный статус; `null` — все статусы. */
  status: GuidelineStatus | null
  /** Выбранный код МКБ; `null` — фильтра по коду нет. */
  icd?: string | null
}

/** Какое состояние показывать при текущих данных. */
export function selectListView({ isLoading, error, count, status, icd }: ListViewInput): ListView {
  if (isLoading) {
    return { kind: 'loading' }
  }
  if (error !== null) {
    return { kind: 'error', message: error }
  }
  if (count === 0) {
    return { kind: 'empty', filtered: status !== null || (icd ?? null) !== null }
  }
  return { kind: 'list' }
}
