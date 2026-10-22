/**
 * Состояние удаления клинрека: подтверждение, выполнение и отказ.
 *
 * Подтверждение — это состояние, а не окно браузера: только так можно проверить тестом,
 * что запрос не уходит до согласия, и показать причину отказа в самой строке.
 */

import { ApiError, describeError } from '../api/client'

/** Фаза удаления одной строки списка. */
export type DeletePhase = 'idle' | 'confirming' | 'deleting' | 'error'

export type DeleteState =
  | { kind: 'idle' }
  | { kind: 'confirming'; guidelineId: string }
  | { kind: 'deleting'; guidelineId: string }
  | { kind: 'error'; guidelineId: string; message: string }

/** Ничего не удаляется. */
export const IDLE_DELETE: DeleteState = { kind: 'idle' }

/** Спросить подтверждение; запрос на сервер ещё не уходит. */
export function requestDelete(state: DeleteState, guidelineId: string): DeleteState {
  if (state.kind === 'deleting') {
    return state
  }
  return { kind: 'confirming', guidelineId }
}

/** Отменить подтверждение или скрыть сообщение об отказе. */
export function cancelDelete(state: DeleteState): DeleteState {
  return state.kind === 'deleting' ? state : IDLE_DELETE
}

/** Перейти к выполнению после подтверждения. */
export function startDelete(state: DeleteState): DeleteState {
  return state.kind === 'confirming' ? { kind: 'deleting', guidelineId: state.guidelineId } : state
}

/** Записать отказ удаления с читаемой причиной. */
export function failDelete(state: DeleteState, error: unknown): DeleteState {
  if (state.kind === 'idle') {
    return state
  }
  return { kind: 'error', guidelineId: state.guidelineId, message: describeDeleteError(error) }
}

/** Фаза удаления для конкретной строки: остальные строки остаются в покое. */
export function deletePhaseFor(state: DeleteState, guidelineId: string): DeletePhase {
  return state.kind !== 'idle' && state.guidelineId === guidelineId ? state.kind : 'idle'
}

/** Сообщение об отказе для конкретной строки. */
export function deleteErrorFor(state: DeleteState, guidelineId: string): string | null {
  return state.kind === 'error' && state.guidelineId === guidelineId ? state.message : null
}

/** Спрятать удалённый клинрек из списка, не дожидаясь перезагрузки. */
export function hideGuideline(guidelineIds: readonly string[], guidelineId: string): string[] {
  return guidelineIds.includes(guidelineId) ? [...guidelineIds] : [...guidelineIds, guidelineId]
}

/** Читаемая причина отказа удаления: коды ответов важнее текста сервера. */
export function describeDeleteError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return 'Клинрек не найден — возможно, он уже удалён. Обновите список.'
    }
    if (error.status === 409) {
      return 'По клинреку идёт индексация. Удаление станет доступно после её окончания.'
    }
    if (error.status === 503) {
      return 'Векторное хранилище недоступно, поэтому клинрек не удалён. Повторите позже.'
    }
  }
  return describeError(error)
}
