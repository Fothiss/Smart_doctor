import { describe, expect, it } from 'vitest'

import { ApiError, SERVER_UNAVAILABLE_MESSAGE } from '../api/client'
import { describeUploadError } from './uploadErrors'

describe('describeUploadError', () => {
  it('400 — файл не принят, причина переводится', () => {
    const problem = describeUploadError(new ApiError(400, 'file is not a PDF'))

    expect(problem.kind).toBe('invalid-file')
    expect(problem.message).toBe('Файл не принят: файл не является PDF')
  })

  it('400 — неизвестный текст сервера показывается как есть', () => {
    const problem = describeUploadError(new ApiError(400, 'unexpected backend text'))

    expect(problem.kind).toBe('invalid-file')
    expect(problem.message).toContain('unexpected backend text')
  })

  it('413 — превышение размера с лимитом из сообщения', () => {
    const problem = describeUploadError(new ApiError(413, 'file exceeds 50 MB'))

    expect(problem.kind).toBe('too-large')
    expect(problem.message).toBe('Файл превышает допустимый размер (50 MB)')
  })

  it('413 без лимита в тексте', () => {
    const problem = describeUploadError(new ApiError(413, 'too large'))

    expect(problem.message).toBe('Файл превышает допустимый размер')
  })

  it('409 — дубликат со ссылкой на существующий клинрек', () => {
    const problem = describeUploadError(
      new ApiError(409, 'guideline with the same content already exists', 'abc-123'),
    )

    expect(problem).toEqual({
      kind: 'duplicate',
      message: 'PDF с таким содержимым уже загружен',
      guidelineId: 'abc-123',
    })
  })

  it('409 без идентификатора не даёт битую ссылку', () => {
    const problem = describeUploadError(new ApiError(409, 'duplicate'))

    expect(problem.kind).toBe('duplicate')
    expect(problem.kind === 'duplicate' && problem.guidelineId).toBeNull()
  })

  it('недоступный сервер показывается как есть', () => {
    const problem = describeUploadError(new ApiError(0, SERVER_UNAVAILABLE_MESSAGE))

    expect(problem.kind).toBe('unknown')
    expect(problem.message).toBe(SERVER_UNAVAILABLE_MESSAGE)
  })

  it('ошибка не из API не раскрывает внутренностей', () => {
    expect(describeUploadError(new Error('boom')).message).toBe('Не удалось загрузить клинрек')
    expect(describeUploadError('строка').message).toBe('Не удалось загрузить клинрек')
  })
})
