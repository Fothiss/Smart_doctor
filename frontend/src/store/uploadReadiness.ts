/**
 * Готовность формы загрузки к отправке.
 *
 * Вынесено из компонента: без этого правило «файл, коды МКБ и отсутствие ошибок формата»
 * нельзя проверить тестом без DOM, а именно оно решает, уйдёт ли запрос на сервер.
 */

import type { ParsedIcd } from '../lib/icd'

export type UploadReadinessInput = {
  /** Выбран ли файл. */
  hasFile: boolean
  /** Идёт ли передача прямо сейчас. */
  isUploading: boolean
  /** Разобранный ввод кодов МКБ. */
  parsed: ParsedIcd
}

/** Можно ли отправлять форму загрузки. */
export function canSubmitUpload({ hasFile, isUploading, parsed }: UploadReadinessInput): boolean {
  return hasFile && !isUploading && parsed.codes.length > 0 && parsed.invalid.length === 0
}
