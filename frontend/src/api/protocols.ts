/** Клиент валидации черновика протокола; типы берутся из сгенерированной схемы. */

import { postJson } from './client'
import type { components } from './schema'

export type ProtocolDraftRequest = components['schemas']['ProtocolDraftRequest']
export type ProtocolDraftResponse = components['schemas']['ProtocolDraftResponse']
export type ProtocolForm = components['schemas']['ProtocolForm']
export type ProtocolPrescription = components['schemas']['ProtocolPrescription']
export type ProtocolGuidelineRef = components['schemas']['ProtocolGuidelineRef']

/** Адрес валидации черновика. */
export const PROTOCOL_VALIDATE_PATH = '/api/protocols/validate'

/**
 * Проверить черновик на сервере.
 *
 * Сервер не сохраняет форму: ответ содержит подтверждённую форму, сведения о клинреке и
 * атомарные пункты, которые пойдут в проверку.
 */
export async function validateProtocol(
  draft: ProtocolDraftRequest,
  init?: RequestInit,
): Promise<ProtocolDraftResponse> {
  return postJson<ProtocolDraftResponse>(PROTOCOL_VALIDATE_PATH, draft, init)
}
