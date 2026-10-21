/**
 * Чистая логика списка клинреков: слияние страниц, фильтр, признак «есть ещё».
 *
 * Состояние отделено от React и от сети: его можно проверить тестом без DOM, а хук
 * `useGuidelineList` остаётся тонкой обвязкой над этими функциями.
 */

import type { Guideline, GuidelineStatus } from '../api/guidelines'
import { guidelinesListPath } from '../api/guidelines'

export type GuidelineListState = {
  items: Guideline[]
  /** Смещение следующего запроса. */
  nextOffset: number
  /** Сервер вернул полную страницу — возможно, есть ещё. */
  hasMore: boolean
  /** Текущий фильтр; `null` — все статусы. */
  status: GuidelineStatus | null
  /** Текущий фильтр по коду МКБ; `null` — любой код. */
  icd: string | null
}

/** Пустое состояние списка для заданных фильтров. */
export function initialListState(
  status: GuidelineStatus | null,
  icd: string | null = null,
): GuidelineListState {
  return { items: [], nextOffset: 0, hasMore: true, status, icd }
}

/** Сменить фильтры: накопленные страницы другого фильтра не смешиваются с новыми. */
export function applyFilter(
  state: GuidelineListState,
  status: GuidelineStatus | null,
  icd: string | null = null,
): GuidelineListState {
  if (state.status === status && state.icd === icd) {
    return state
  }
  return initialListState(status, icd)
}

/**
 * Добавить полученную страницу к списку.
 *
 * Дубликаты по `guideline_id` отбрасываются: догрузка не должна показывать один клинрек дважды,
 * даже если сервер вернул пересекающуюся страницу.
 */
export function mergePage(
  state: GuidelineListState,
  page: readonly Guideline[],
  pageSize: number,
): GuidelineListState {
  const known = new Set(state.items.map((item) => item.guideline_id))
  const fresh = page.filter((item) => !known.has(item.guideline_id))
  return {
    items: [...state.items, ...fresh],
    nextOffset: state.nextOffset + page.length,
    hasMore: page.length === pageSize,
    status: state.status,
    icd: state.icd,
  }
}

/** Адрес следующей страницы для текущего состояния. */
export function nextPagePath(state: GuidelineListState, pageSize: number): string {
  return guidelinesListPath({
    status: state.status,
    icd: state.icd,
    limit: pageSize,
    offset: state.nextOffset,
  })
}
