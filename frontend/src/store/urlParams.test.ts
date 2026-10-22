import { describe, expect, it } from 'vitest'

import {
  ICD_PARAM,
  OFFSET_PARAM,
  PAGE_PARAM,
  STATUS_PARAM,
  readBackTarget,
  readIcd,
  readOffset,
  readPage,
  readStatus,
  writeIcd,
  writeOffset,
  writeStatus,
} from './urlParams'

function params(init: string): URLSearchParams {
  return new URLSearchParams(init)
}

describe('readStatus', () => {
  it('читает известный статус', () => {
    expect(readStatus(params('status=uploaded'))).toBe('uploaded')
    expect(readStatus(params('status=failed'))).toBe('failed')
  })

  it('не пропускает неизвестное значение', () => {
    expect(readStatus(params('status=нечто'))).toBeNull()
  })

  it('без параметра — все статусы', () => {
    expect(readStatus(params(''))).toBeNull()
  })
})

describe('readOffset', () => {
  it('читает неотрицательное число', () => {
    expect(readOffset(params('offset=50'))).toBe(50)
    expect(readOffset(params('offset=0'))).toBe(0)
  })

  it('отбрасывает мусор и отрицательные значения', () => {
    expect(readOffset(params('offset=-5'))).toBe(0)
    expect(readOffset(params('offset=abc'))).toBe(0)
    expect(readOffset(params('offset=1.5'))).toBe(0)
    expect(readOffset(params(''))).toBe(0)
  })
})

describe('readPage', () => {
  it('читает номер страницы', () => {
    expect(readPage(params('page=12'))).toBe(12)
  })

  it('без параметра — первая страница', () => {
    expect(readPage(params(''))).toBe(1)
  })

  it('мусор и ноль дают первую страницу', () => {
    expect(readPage(params('page=abc'))).toBe(1)
    expect(readPage(params('page=0'))).toBe(1)
    expect(readPage(params('page=-3'))).toBe(1)
  })
})

describe('writeStatus', () => {
  it('записывает фильтр и сбрасывает смещение', () => {
    const next = writeStatus(params('offset=100'), 'ready')

    expect(next.get(STATUS_PARAM)).toBe('ready')
    expect(next.get(OFFSET_PARAM)).toBeNull()
  })

  it('удаляет фильтр при сбросе', () => {
    const next = writeStatus(params('status=ready&offset=50'), null)

    expect(next.get(STATUS_PARAM)).toBeNull()
    expect(next.get(OFFSET_PARAM)).toBeNull()
  })
})

describe('writeOffset', () => {
  it('записывает смещение и сохраняет фильтр', () => {
    const next = writeOffset(params('status=ready'), 50)

    expect(next.get(OFFSET_PARAM)).toBe('50')
    expect(next.get(STATUS_PARAM)).toBe('ready')
  })

  it('убирает нулевое смещение из адреса', () => {
    expect(writeOffset(params('offset=50'), 0).get(OFFSET_PARAM)).toBeNull()
  })
})

describe('readIcd', () => {
  it('читает код и поднимает регистр', () => {
    expect(readIcd(params('icd=i10'))).toBe('I10')
    expect(readIcd(params('icd=I10.1'))).toBe('I10.1')
  })

  it('мусор в параметре не даёт фильтра', () => {
    expect(readIcd(params('icd=гипертензия'))).toBeNull()
    expect(readIcd(params('icd=I1'))).toBeNull()
    expect(readIcd(params(''))).toBeNull()
  })
})

describe('writeIcd', () => {
  it('записывает нормализованный код и сбрасывает смещение', () => {
    const next = writeIcd(params('offset=100'), ' i10 ')

    expect(next.get(ICD_PARAM)).toBe('I10')
    expect(next.get(OFFSET_PARAM)).toBeNull()
  })

  it('не ломает фильтр по статусу', () => {
    const next = writeIcd(params('status=ready'), 'I10')

    expect(next.get(STATUS_PARAM)).toBe('ready')
    expect(next.get(ICD_PARAM)).toBe('I10')
  })

  it('удаляет параметр при сбросе и при невалидном коде', () => {
    expect(writeIcd(params('icd=I10&offset=50'), null).get(ICD_PARAM)).toBeNull()
    expect(writeIcd(params('icd=I10'), 'мусор').get(ICD_PARAM)).toBeNull()
  })
})

describe('параметры не смешиваются', () => {
  it('номер страницы просмотра не мешает фильтру списка', () => {
    const next = writeStatus(params(`${PAGE_PARAM}=3`), 'uploaded')

    expect(next.get(PAGE_PARAM)).toBe('3')
    expect(next.get(STATUS_PARAM)).toBe('uploaded')
  })
})

describe('readBackTarget', () => {
  it('возвращает состояние библиотеки из перехода', () => {
    expect(readBackTarget({ from: '/library?status=ready&offset=50' })).toBe(
      '/library?status=ready&offset=50',
    )
  })

  it('без состояния ведёт в библиотеку', () => {
    expect(readBackTarget(undefined)).toBe('/library')
    expect(readBackTarget(null)).toBe('/library')
    expect(readBackTarget({})).toBe('/library')
  })

  it('игнорирует чужой адрес', () => {
    expect(readBackTarget({ from: '/evil' })).toBe('/library')
    expect(readBackTarget({ from: 'https://example.com' })).toBe('/library')
    expect(readBackTarget({ from: 42 })).toBe('/library')
  })
})
