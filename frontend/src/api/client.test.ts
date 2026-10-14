import { describe, expect, it } from 'vitest'

import { ApiError, apiErrorFromResponse, parseErrorDetail } from './client'

describe('parseErrorDetail', () => {
  it('берёт сообщение из строкового detail', () => {
    const parsed = parseErrorDetail(400, { detail: 'only PDF files are supported' })

    expect(parsed).toEqual({ message: 'only PDF files are supported', guidelineId: null })
  })

  it('берёт сообщение и guideline_id из объектного detail', () => {
    const parsed = parseErrorDetail(409, {
      detail: {
        message: 'guideline with the same content already exists',
        guideline_id: 'a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7',
      },
    })

    expect(parsed).toEqual({
      message: 'guideline with the same content already exists',
      guidelineId: 'a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7',
    })
  })

  it('возвращает null вместо идентификатора, если объект без guideline_id', () => {
    const parsed = parseErrorDetail(409, { detail: { message: 'duplicate' } })

    expect(parsed.message).toBe('duplicate')
    expect(parsed.guidelineId).toBeNull()
  })

  it('сообщает код, когда detail отсутствует', () => {
    expect(parseErrorDetail(500, {})).toEqual({
      message: 'Сервер ответил ошибкой 500',
      guidelineId: null,
    })
  })

  it('не падает на теле, которое не является объектом', () => {
    expect(parseErrorDetail(502, 'gateway timeout').message).toBe('Сервер ответил ошибкой 502')
    expect(parseErrorDetail(502, null).message).toBe('Сервер ответил ошибкой 502')
    expect(parseErrorDetail(502, ['detail']).message).toBe('Сервер ответил ошибкой 502')
  })

  it('склеивает сообщения валидации FastAPI', () => {
    const parsed = parseErrorDetail(422, {
      detail: [
        { loc: ['query', 'limit'], msg: 'Input should be greater than or equal to 1', type: 'x' },
        { loc: ['query', 'offset'], msg: 'Input should be greater than or equal to 0', type: 'y' },
      ],
    })

    expect(parsed.message).toBe(
      'Input should be greater than or equal to 1; Input should be greater than or equal to 0',
    )
  })

  it('игнорирует пустую строку в detail', () => {
    expect(parseErrorDetail(404, { detail: '   ' }).message).toBe('Сервер ответил ошибкой 404')
  })
})

describe('apiErrorFromResponse', () => {
  it('разбирает JSON-тело ошибки', () => {
    const error = apiErrorFromResponse(404, '{"detail":"guideline not found"}')

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('guideline not found')
  })

  it('переживает не-JSON тело', () => {
    const error = apiErrorFromResponse(500, '<html>Internal Server Error</html>')

    expect(error.status).toBe(500)
    expect(error.message).toBe('Сервер ответил ошибкой 500')
  })

  it('переживает пустое тело', () => {
    expect(apiErrorFromResponse(413, '').message).toBe('Сервер ответил ошибкой 413')
  })
})

describe('отказы загрузки клинрека', () => {
  it('400 — пустой файл или не PDF', () => {
    const error = apiErrorFromResponse(400, '{"detail":"file is not a PDF"}')

    expect(error.status).toBe(400)
    expect(error.message).toBe('file is not a PDF')
    expect(error.guidelineId).toBeNull()
  })

  it('413 — превышение размера', () => {
    const error = apiErrorFromResponse(413, '{"detail":"file exceeds 50 MB"}')

    expect(error.status).toBe(413)
    expect(error.message).toBe('file exceeds 50 MB')
  })

  it('409 — дубликат с идентификатором существующего клинрека', () => {
    const error = apiErrorFromResponse(
      409,
      '{"detail":{"message":"guideline with the same content already exists","guideline_id":"5fc51635-7cdf-4efe-99dd-fa7028434376"}}',
    )

    expect(error.status).toBe(409)
    expect(error.guidelineId).toBe('5fc51635-7cdf-4efe-99dd-fa7028434376')
  })

  it('409 без идентификатора не даёт ссылку на несуществующий клинрек', () => {
    const error = apiErrorFromResponse(409, '{"detail":{"message":"duplicate"}}')

    expect(error.status).toBe(409)
    expect(error.guidelineId).toBeNull()
  })
})
