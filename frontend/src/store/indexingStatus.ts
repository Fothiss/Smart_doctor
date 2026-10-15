/**
 * Правило опроса статусов индексации.
 *
 * Чистые функции: React их не касается, поэтому проверяются тестами без браузера.
 * Опрашивать нужно только те клинреки, состояние которых ещё может измениться —
 * иначе страница бесконечно дёргает сервер после завершения обработки.
 */

import type { Guideline, GuidelineStatus } from '../api/guidelines'

/** Интервал опроса: индексация идёт минутами, чаще спрашивать незачем. */
export const POLL_INTERVAL_MS = 2500

/** Окончательные статусы: после них состояние клинрека само не изменится. */
export const FINAL_STATUSES: readonly GuidelineStatus[] = ['ready', 'failed']

/** Может ли статус измениться сам. */
export function isFinalStatus(status: GuidelineStatus): boolean {
  return FINAL_STATUSES.includes(status)
}

/** Нужно ли опрашивать этот клинрек. */
export function needsPolling(guideline: Pick<Guideline, 'status'>): boolean {
  return !isFinalStatus(guideline.status)
}

/** Есть ли в списке хоть один клинрек, который стоит опрашивать. */
export function needsPollingList(guidelines: readonly Pick<Guideline, 'status'>[]): boolean {
  return guidelines.some(needsPolling)
}

/** Описание хода индексации для интерфейса; `null` — показывать нечего. */
export function describeProgress(guideline: Guideline): string | null {
  if (guideline.status !== 'processing') {
    return null
  }
  const total = guideline.chunks_total ?? null
  if (total === null || total === 0) {
    return 'Обработка идёт: документ читается'
  }
  const indexed = guideline.chunks_indexed ?? 0
  return `Обработано ${indexed} из ${total} фрагментов`
}

/**
 * Признак векторизации для готового клинрека.
 *
 * `null` для всех остальных статусов: пока сервер не сказал `ready`, показывать
 * «векторизован» нельзя — это обещание, которого документ не выполняет.
 */
export function describeVectorization(guideline: Guideline): string | null {
  if (guideline.status !== 'ready') {
    return null
  }
  const parts = ['Векторизован']
  if (guideline.chunks_total != null) {
    parts.push(`${guideline.chunks_total} фрагментов`)
  }
  if (guideline.embedding_model != null && guideline.embedding_model !== '') {
    parts.push(guideline.embedding_model)
  }
  return parts.join(' · ')
}
