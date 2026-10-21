import { describe, expect, it } from 'vitest'

import { parseIcdInput } from '../lib/icd'
import { canSubmitUpload } from './uploadReadiness'

describe('canSubmitUpload', () => {
  it('без файла отправка недоступна', () => {
    expect(
      canSubmitUpload({ hasFile: false, isUploading: false, parsed: parseIcdInput('I10') }),
    ).toBe(false)
  })

  it('без кодов МКБ отправка недоступна', () => {
    expect(
      canSubmitUpload({ hasFile: true, isUploading: false, parsed: parseIcdInput('') }),
    ).toBe(false)
  })

  it('код вне формата блокирует отправку', () => {
    expect(
      canSubmitUpload({
        hasFile: true,
        isUploading: false,
        parsed: parseIcdInput('I10, гипертензия'),
      }),
    ).toBe(false)
  })

  it('во время передачи повторная отправка недоступна', () => {
    expect(
      canSubmitUpload({ hasFile: true, isUploading: true, parsed: parseIcdInput('I10') }),
    ).toBe(false)
  })

  it('файл и хотя бы один корректный код разрешают отправку', () => {
    expect(
      canSubmitUpload({ hasFile: true, isUploading: false, parsed: parseIcdInput('i10, I15') }),
    ).toBe(true)
  })
})
