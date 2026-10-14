/**
 * Чтение и запись параметров адреса.
 *
 * Фильтр списка и номер страницы просмотра живут в query-параметрах, поэтому состояние экрана
 * переживает переход в просмотрщик и обратно, а ссылкой можно поделиться.
 */

import { type GuidelineStatus, isGuidelineStatus } from '../api/guidelines'

export const STATUS_PARAM = 'status'
export const OFFSET_PARAM = 'offset'
export const PAGE_PARAM = 'page'

/** Прочитать фильтр списка; неизвестное значение трактуется как «все статусы». */
export function readStatus(params: URLSearchParams): GuidelineStatus | null {
  const raw = params.get(STATUS_PARAM)
  return isGuidelineStatus(raw) ? raw : null
}

/** Прочитать смещение списка; отрицательное и нечисловое значение — ноль. */
export function readOffset(params: URLSearchParams): number {
  return readNonNegativeInt(params.get(OFFSET_PARAM), 0)
}

/** Прочитать номер страницы просмотра; отсутствующий или мусорный — первая страница. */
export function readPage(params: URLSearchParams): number {
  return readNonNegativeInt(params.get(PAGE_PARAM), 1) || 1
}

/** Записать фильтр списка: смена фильтра начинает список с начала. */
export function writeStatus(params: URLSearchParams, status: GuidelineStatus | null): URLSearchParams {
  const next = new URLSearchParams(params)
  if (status === null) {
    next.delete(STATUS_PARAM)
  } else {
    next.set(STATUS_PARAM, status)
  }
  next.delete(OFFSET_PARAM)
  return next
}

/** Записать смещение списка. */
export function writeOffset(params: URLSearchParams, offset: number): URLSearchParams {
  const next = new URLSearchParams(params)
  if (offset > 0) {
    next.set(OFFSET_PARAM, String(offset))
  } else {
    next.delete(OFFSET_PARAM)
  }
  return next
}

function readNonNegativeInt(raw: string | null, fallback: number): number {
  if (raw === null) {
    return fallback
  }
  const parsed = Number(raw)
  if (!Number.isInteger(parsed) || parsed < 0) {
    return fallback
  }
  return parsed
}

/**
 * Адрес возврата из просмотрщика в библиотеку.
 *
 * Экран списка передаёт своё состояние (фильтр и позицию) в состоянии перехода, поэтому возврат
 * не теряет ни фильтр, ни загруженные страницы. Любое чужое значение игнорируется.
 */
export function readBackTarget(state: unknown): string {
  if (typeof state === 'object' && state !== null && 'from' in state) {
    const { from } = state as { from?: unknown }
    if (typeof from === 'string' && from.startsWith('/library')) {
      return from
    }
  }
  return '/library'
}
