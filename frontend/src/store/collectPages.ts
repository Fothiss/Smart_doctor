/**
 * Загрузка страниц списка клинреков.
 *
 * Сеть приходит сюда функцией `fetchPage`, поэтому порядок и параметры запросов проверяются
 * тестом с подменённым `fetch`, а хук `useGuidelineList` остаётся тонкой обвязкой.
 */

import type { Guideline, GuidelineListParams, GuidelineStatus } from '../api/guidelines'
import { type GuidelineListState, initialListState, mergePage } from './guidelineList'

/** Загрузка одной страницы; в приложении — `listGuidelines`. */
export type FetchPage = (
  params: GuidelineListParams & { limit: number; offset: number },
  init?: RequestInit,
) => Promise<Guideline[]>

/**
 * Набрать страницы от начала списка до `targetOffset` включительно.
 *
 * Нужно для восстановления позиции из адреса: после возврата из просмотрщика список должен
 * содержать те же записи, а не одну первую страницу. Короткая страница завершает набор.
 */
export async function collectPages(
  fetchPage: FetchPage,
  status: GuidelineStatus | null,
  icd: string | null,
  targetOffset: number,
  pageSize: number,
  init?: RequestInit,
): Promise<GuidelineListState> {
  let accumulated = initialListState(status, icd)
  while (accumulated.hasMore && accumulated.nextOffset <= targetOffset) {
    const page = await fetchPage(
      { status, icd, limit: pageSize, offset: accumulated.nextOffset },
      init,
    )
    accumulated = mergePage(accumulated, page, pageSize)
  }
  return accumulated
}

/** Загрузить следующую страницу и добавить её к состоянию. */
export async function loadNextPage(
  fetchPage: FetchPage,
  state: GuidelineListState,
  pageSize: number,
): Promise<GuidelineListState> {
  const page = await fetchPage({
    status: state.status,
    icd: state.icd,
    limit: pageSize,
    offset: state.nextOffset,
  })
  return mergePage(state, page, pageSize)
}
