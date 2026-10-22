import { describe, expect, it } from 'vitest'

import {
  DEFAULT_PAGE_SIZE,
  GUIDELINE_STATUSES,
  GUIDELINE_STATUS_LABELS,
  buildListQuery,
  buildUploadForm,
  guidelineFileUrl,
  guidelinePath,
  guidelinesListPath,
  isGuidelineStatus,
} from './guidelines'

describe('buildListQuery', () => {
  it('не отправляет незаданные параметры', () => {
    expect(buildListQuery({})).toBe('')
  })

  it('передаёт фильтр по статусу', () => {
    expect(buildListQuery({ status: 'uploaded' })).toBe('?status=uploaded')
  })

  it('не отправляет status = null как значение', () => {
    expect(buildListQuery({ status: null, limit: 10, offset: 0 })).toBe('?limit=10&offset=0')
  })

  it('передаёт фильтр по коду МКБ', () => {
    expect(buildListQuery({ icd: 'I10' })).toBe('?icd=I10')
  })

  it('не отправляет пустой код МКБ', () => {
    expect(buildListQuery({ icd: '' })).toBe('')
    expect(buildListQuery({ icd: null })).toBe('')
  })

  it('передаёт пагинацию', () => {
    expect(buildListQuery({ limit: 50, offset: 100 })).toBe('?limit=50&offset=100')
  })
})

describe('guidelinesListPath', () => {
  it('подставляет размер страницы и смещение по умолчанию', () => {
    expect(guidelinesListPath()).toBe(`/api/guidelines?limit=${DEFAULT_PAGE_SIZE}&offset=0`)
  })

  it('передаёт фильтр и смещение догрузки', () => {
    expect(guidelinesListPath({ status: 'ready', offset: 50 })).toBe(
      `/api/guidelines?status=ready&limit=${DEFAULT_PAGE_SIZE}&offset=50`,
    )
  })

  it('уважает явный размер страницы', () => {
    expect(guidelinesListPath({ limit: 10, offset: 20 })).toBe('/api/guidelines?limit=10&offset=20')
  })

  it('передаёт код МКБ в списке', () => {
    expect(guidelinesListPath({ icd: 'I10' })).toBe(
      `/api/guidelines?icd=I10&limit=${DEFAULT_PAGE_SIZE}&offset=0`,
    )
  })
})

describe('guidelinePath', () => {
  it('собирает адрес клинрека и кодирует идентификатор', () => {
    expect(guidelinePath('a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7')).toBe(
      '/api/guidelines/a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7',
    )
    expect(guidelinePath('a b')).toBe('/api/guidelines/a%20b')
  })
})

describe('buildUploadForm', () => {
  const file = new File(['%PDF-1.7'], 'klinrek.pdf', { type: 'application/pdf' })

  it('отправляет коды МКБ повторяющимся полем', () => {
    const form = buildUploadForm({ file, icdCodes: ['I10', 'I15'] })

    expect(form.getAll('icd_codes')).toEqual(['I10', 'I15'])
    expect(form.get('title')).toBeNull()
  })

  it('добавляет название, если оно заполнено', () => {
    const form = buildUploadForm({ file, title: '  Гипертензия ', icdCodes: ['I10'] })

    expect(form.get('title')).toBe('Гипертензия')
  })

  it('не отправляет пустое название', () => {
    const form = buildUploadForm({ file, title: '   ', icdCodes: ['I10'] })

    expect(form.get('title')).toBeNull()
  })
})

describe('guidelineFileUrl', () => {
  it('собирает адрес оригинала', () => {
    expect(guidelineFileUrl('a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7')).toBe(
      '/api/guidelines/a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7/file',
    )
  })

  it('добавляет версию документа, если она задана', () => {
    expect(guidelineFileUrl('abc', 2)).toBe('/api/guidelines/abc/file?version=2')
    expect(guidelineFileUrl('abc', 1)).toBe('/api/guidelines/abc/file?version=1')
  })

  it('кодирует идентификатор в адресе', () => {
    expect(guidelineFileUrl('a b')).toBe('/api/guidelines/a%20b/file')
  })
})

describe('подписи статусов', () => {
  it('покрывают все значения схемы', () => {
    expect(Object.keys(GUIDELINE_STATUS_LABELS).sort()).toEqual([...GUIDELINE_STATUSES].sort())
  })

  it('не обещают готовность к проверке для статуса uploaded', () => {
    expect(GUIDELINE_STATUS_LABELS.uploaded).toBe('Загружен')
    expect(GUIDELINE_STATUS_LABELS.ready).toBe('Готов к проверке')
  })
})

describe('isGuidelineStatus', () => {
  it('принимает значения схемы', () => {
    for (const status of GUIDELINE_STATUSES) {
      expect(isGuidelineStatus(status)).toBe(true)
    }
  })

  it('отклоняет мусор', () => {
    expect(isGuidelineStatus('unknown')).toBe(false)
    expect(isGuidelineStatus(null)).toBe(false)
    expect(isGuidelineStatus(undefined)).toBe(false)
    expect(isGuidelineStatus(1)).toBe(false)
  })
})
