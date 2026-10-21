import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import { PROTOCOL_VALIDATE_PATH } from '../api/protocols'
import { describeValidationError } from './protocolErrors'

describe('describeValidationError', () => {
  it('на 400 показывает причину сервера с именем поля', () => {
    const message = describeValidationError(new ApiError(400, 'complaints: value is required'))

    expect(message).toBe('Форма отклонена: complaints: value is required')
  })

  it('на 404 объясняет, что клинрека больше нет', () => {
    expect(describeValidationError(new ApiError(404, 'not found'))).toContain('Клинрек не найден')
  })

  it('на 409 объясняет, что клинрек не готов', () => {
    expect(describeValidationError(new ApiError(409, 'uploaded'))).toContain('не готов')
  })

  it('прочие ошибки показывает как есть', () => {
    expect(describeValidationError(new ApiError(0, 'Сервер недоступен'))).toBe(
      'Сервер недоступен',
    )
    expect(describeValidationError('строка')).toBe('Неизвестная ошибка')
  })

  it('адрес валидации один для клиента и проверок', () => {
    expect(PROTOCOL_VALIDATE_PATH).toBe('/api/protocols/validate')
  })
})
