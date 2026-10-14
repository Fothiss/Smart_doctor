/**
 * Транспорт к API: единая ошибка и разбор формата `{"detail": ...}`.
 *
 * Бэкенд отвечает `detail` строкой для 400/404/413 и объектом
 * `{message, guideline_id}` для 409, а ошибки валидации FastAPI — массивом объектов.
 * Клиент обязан понимать все три вида: иначе сообщение объекта уйдёт в интерфейс как
 * `[object Object]`, а идентификатор дубликата потеряется.
 */

/** Ошибка обращения к API: HTTP-статус и читаемое сообщение. */
export class ApiError extends Error {
  /** HTTP-код ответа; `0` — запрос не дошёл до сервера. */
  readonly status: number

  /** Идентификатор существующего клинрека из ответа 409, если сервер его передал. */
  readonly guidelineId: string | null

  constructor(status: number, message: string, guidelineId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.guidelineId = guidelineId
  }
}

/** Сообщение, когда сервер недоступен: процесс не запущен, порт занят, обрыв сети. */
export const SERVER_UNAVAILABLE_MESSAGE =
  'Сервер недоступен. Проверьте, что бэкенд запущен на 127.0.0.1:8000.'

/** Разобранное тело ошибки. */
export type ParsedErrorDetail = {
  message: string
  guidelineId: string | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/** Тексты ошибок валидации FastAPI: `detail` — массив объектов с полем `msg`. */
function messageFromValidationArray(detail: readonly unknown[]): string | null {
  const messages = detail
    .map((item) => (isRecord(item) ? nonEmptyString(item.msg) : null))
    .filter((msg): msg is string => msg !== null)
  return messages.length > 0 ? messages.join('; ') : null
}

/**
 * Разобрать тело ошибки в сообщение и идентификатор клинрека.
 *
 * Неизвестная форма тела не считается ошибкой клиента: возвращается сообщение по коду.
 */
export function parseErrorDetail(status: number, body: unknown): ParsedErrorDetail {
  const fallbackMessage = `Сервер ответил ошибкой ${status}`
  if (!isRecord(body)) {
    return { message: fallbackMessage, guidelineId: null }
  }

  const detail = body.detail
  const asString = nonEmptyString(detail)
  if (asString !== null) {
    return { message: asString, guidelineId: null }
  }

  if (Array.isArray(detail)) {
    const message = messageFromValidationArray(detail)
    return { message: message ?? fallbackMessage, guidelineId: null }
  }

  if (isRecord(detail)) {
    return {
      message: nonEmptyString(detail.message) ?? fallbackMessage,
      guidelineId: nonEmptyString(detail.guideline_id),
    }
  }

  return { message: fallbackMessage, guidelineId: null }
}

/** Разобрать тело как JSON; пустое или не-JSON тело не должно ронять клиент. */
function parseJson(raw: string): unknown {
  if (raw.trim() === '') {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/** Собрать `ApiError` из статуса и сырого тела ответа. */
export function apiErrorFromResponse(status: number, rawBody: string): ApiError {
  const { message, guidelineId } = parseErrorDetail(status, parseJson(rawBody))
  return new ApiError(status, message, guidelineId)
}

/** Сообщение для интерфейса из любой пойманной ошибки. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message
  }
  return 'Неизвестная ошибка'
}

/** Выполнить запрос и вернуть разобранный JSON. */
export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' }, ...init })
  } catch {
    throw new ApiError(0, SERVER_UNAVAILABLE_MESSAGE)
  }

  const raw = await response.text()
  if (!response.ok) {
    throw apiErrorFromResponse(response.status, raw)
  }
  return parseJson(raw) as T
}
