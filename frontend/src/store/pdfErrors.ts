/**
 * Причины, по которым оригинал клинрека не удалось показать.
 *
 * PDF.js при 404 бросает исключение со свойством `status`; всё остальное (повреждённый файл,
 * обрыв соединения) выглядит для пользователя одинаково.
 */

export const PDF_NOT_FOUND_MESSAGE = 'Оригинал документа недоступен: файл не найден на сервере'
export const PDF_BROKEN_MESSAGE = 'Не удалось отобразить документ: файл повреждён или недоступен'

/** Сообщение для интерфейса по ошибке PDF.js. */
export function describePdfError(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'status' in error) {
    const { status } = error as { status?: unknown }
    if (status === 404) {
      return PDF_NOT_FOUND_MESSAGE
    }
  }
  return PDF_BROKEN_MESSAGE
}
