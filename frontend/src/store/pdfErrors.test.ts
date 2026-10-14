import { describe, expect, it } from 'vitest'

import { PDF_BROKEN_MESSAGE, PDF_NOT_FOUND_MESSAGE, describePdfError } from './pdfErrors'

describe('describePdfError', () => {
  it('404 — файла нет на сервере', () => {
    expect(describePdfError({ status: 404, message: 'Unexpected server response (404)' })).toBe(
      PDF_NOT_FOUND_MESSAGE,
    )
  })

  it('повреждённый файл', () => {
    expect(describePdfError(new Error('Invalid PDF structure'))).toBe(PDF_BROKEN_MESSAGE)
  })

  it('не падает на неожиданных значениях', () => {
    expect(describePdfError(undefined)).toBe(PDF_BROKEN_MESSAGE)
    expect(describePdfError(null)).toBe(PDF_BROKEN_MESSAGE)
    expect(describePdfError('строка')).toBe(PDF_BROKEN_MESSAGE)
    expect(describePdfError({ status: 500 })).toBe(PDF_BROKEN_MESSAGE)
  })
})
