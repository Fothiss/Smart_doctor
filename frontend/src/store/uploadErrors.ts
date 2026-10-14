/**
 * Разбор отказов загрузки клинрека в понятный интерфейсу вид.
 *
 * Бэкенд отвечает кодами 400 (пустой файл, не PDF), 413 (превышение размера) и 409 (дубликат
 * с идентификатором уже загруженного клинрека). Отсюда берётся текст для пользователя и ссылка
 * на существующий клинрек.
 */

import { ApiError } from '../api/client'

export type UploadProblem =
  | { kind: 'invalid-file'; message: string }
  | { kind: 'too-large'; message: string }
  | { kind: 'duplicate'; message: string; guidelineId: string | null }
  | { kind: 'unknown'; message: string }

const DUPLICATE_MESSAGE = 'PDF с таким содержимым уже загружен'
const TOO_LARGE_MESSAGE = 'Файл превышает допустимый размер'
const INVALID_FILE_MESSAGE = 'Файл не принят'
const UNKNOWN_MESSAGE = 'Не удалось загрузить клинрек'

/** Тексты бэкенда на русском: ключ — сообщение из `detail`. */
const BACKEND_MESSAGES: Record<string, string> = {
  'file is empty': 'файл пустой',
  'file is not a PDF': 'файл не является PDF',
  'only PDF files are supported': 'поддерживаются только файлы PDF',
  'file name is required': 'не удалось определить имя файла',
}

const EXCEEDS_PATTERN = /^file exceeds (.+)$/

function translate(message: string): string {
  return BACKEND_MESSAGES[message] ?? message
}

/** Описание отказа загрузки для интерфейса. */
export function describeUploadError(error: unknown): UploadProblem {
  if (!(error instanceof ApiError)) {
    return { kind: 'unknown', message: UNKNOWN_MESSAGE }
  }

  if (error.status === 409) {
    return { kind: 'duplicate', message: DUPLICATE_MESSAGE, guidelineId: error.guidelineId }
  }

  if (error.status === 413) {
    const limit = EXCEEDS_PATTERN.exec(error.message)?.[1]
    return {
      kind: 'too-large',
      message: limit === undefined ? TOO_LARGE_MESSAGE : `${TOO_LARGE_MESSAGE} (${limit})`,
    }
  }

  if (error.status === 400) {
    return { kind: 'invalid-file', message: `${INVALID_FILE_MESSAGE}: ${translate(error.message)}` }
  }

  return { kind: 'unknown', message: error.message }
}
