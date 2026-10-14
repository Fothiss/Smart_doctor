/** Клиент эндпоинтов клинреков; типы берутся из сгенерированной схемы `schema.d.ts`. */

import { ApiError, SERVER_UNAVAILABLE_MESSAGE, apiErrorFromResponse, getJson } from './client'
import type { components } from './schema'

export type Guideline = components['schemas']['Guideline']
export type GuidelineStatus = components['schemas']['GuidelineStatus']

/** Значения статуса в порядке схемы сервера. */
export const GUIDELINE_STATUSES: readonly GuidelineStatus[] = [
  'uploaded',
  'processing',
  'ready',
  'failed',
]

/**
 * Подписи статусов для интерфейса.
 *
 * Статус показывается ровно таким, каким его вернул сервер: `uploaded` — «Загружен», а не
 * «готов к проверке», пока ingestion не перевёл клинрек в `ready`.
 */
export const GUIDELINE_STATUS_LABELS: Record<GuidelineStatus, string> = {
  uploaded: 'Загружен',
  processing: 'Обрабатывается',
  ready: 'Готов к проверке',
  failed: 'Ошибка обработки',
}

/** Размер страницы списка по умолчанию. */
export const DEFAULT_PAGE_SIZE = 50

/** Проверка, что строка из адреса — известный статус. */
export function isGuidelineStatus(value: unknown): value is GuidelineStatus {
  return typeof value === 'string' && (GUIDELINE_STATUSES as readonly string[]).includes(value)
}

export type GuidelineListParams = {
  status?: GuidelineStatus | null
  limit?: number
  offset?: number
}

/** Собрать query-строку списка: незаданные параметры в запрос не попадают. */
export function buildListQuery(params: GuidelineListParams): string {
  const search = new URLSearchParams()
  if (params.status != null) {
    search.set('status', params.status)
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    search.set('offset', String(params.offset))
  }
  const query = search.toString()
  return query === '' ? '' : `?${query}`
}

/** Адрес списка клинреков с подставленными значениями по умолчанию. */
export function guidelinesListPath(params: GuidelineListParams = {}): string {
  return `/api/guidelines${buildListQuery({
    status: params.status ?? null,
    limit: params.limit ?? DEFAULT_PAGE_SIZE,
    offset: params.offset ?? 0,
  })}`
}

/** Список клинреков: свежие загрузки первыми (порядок задаёт сервер). */
export async function listGuidelines(
  params: GuidelineListParams = {},
  init?: RequestInit,
): Promise<Guideline[]> {
  return getJson<Guideline[]>(guidelinesListPath(params), init)
}

/** Метаданные и статус одного клинрека. */
export async function getGuideline(guidelineId: string, init?: RequestInit): Promise<Guideline> {
  return getJson<Guideline>(`/api/guidelines/${encodeURIComponent(guidelineId)}`, init)
}

/** Адрес оригинала PDF — его читает PDF.js, опираясь на поддержку `Range` сервером. */
export function guidelineFileUrl(guidelineId: string, version?: number): string {
  const base = `/api/guidelines/${encodeURIComponent(guidelineId)}/file`
  return version === undefined ? base : `${base}?version=${version}`
}

export type UploadGuidelineInput = {
  file: File
  title?: string
  /** Доля переданных байт, 0..1. */
  onProgress?: (fraction: number) => void
  signal?: AbortSignal
}

const UPLOAD_PATH = '/api/guidelines'
const UPLOAD_ABORTED_MESSAGE = 'Загрузка отменена'

/**
 * Загрузить PDF клинрека.
 *
 * Используется `XMLHttpRequest`, а не `fetch`: только он сообщает о ходе отправки, а файлы
 * до 50 МБ без индикатора выглядят как зависший интерфейс.
 */
export function uploadGuideline(input: UploadGuidelineInput): Promise<Guideline> {
  return new Promise<Guideline>((resolve, reject) => {
    const form = new FormData()
    form.append('file', input.file)
    const title = input.title?.trim()
    if (title !== undefined && title !== '') {
      form.append('title', title)
    }

    const request = new XMLHttpRequest()
    request.open('POST', UPLOAD_PATH)
    request.responseType = 'text'

    const { onProgress, signal } = input

    request.upload.onprogress = (event) => {
      if (onProgress !== undefined && event.lengthComputable && event.total > 0) {
        onProgress(event.loaded / event.total)
      }
    }

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        try {
          resolve(JSON.parse(request.responseText) as Guideline)
        } catch {
          reject(new ApiError(request.status, 'Сервер вернул неожиданный ответ'))
        }
        return
      }
      reject(apiErrorFromResponse(request.status, request.responseText))
    }

    request.onerror = () => reject(new ApiError(0, SERVER_UNAVAILABLE_MESSAGE))
    request.onabort = () => reject(new ApiError(0, UPLOAD_ABORTED_MESSAGE))

    if (signal !== undefined) {
      if (signal.aborted) {
        reject(new ApiError(0, UPLOAD_ABORTED_MESSAGE))
        return
      }
      signal.addEventListener('abort', () => request.abort(), { once: true })
    }

    request.send(form)
  })
}
