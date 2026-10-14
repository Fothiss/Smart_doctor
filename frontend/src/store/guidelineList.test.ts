import { describe, expect, it } from 'vitest'

import type { Guideline } from '../api/guidelines'
import {
  applyFilter,
  initialListState,
  mergePage,
  nextPagePath,
} from './guidelineList'

function guideline(id: string): Guideline {
  return {
    guideline_id: id,
    version: 1,
    title: `Клинрек ${id}`,
    filename: `${id}.pdf`,
    size_bytes: 1024,
    sha256: 'a'.repeat(64),
    status: 'uploaded',
    created_at: '2026-10-08T15:54:15.575244Z',
    error: null,
  }
}

const PAGE_SIZE = 2

describe('mergePage', () => {
  it('добавляет первую страницу', () => {
    const state = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)

    expect(state.items.map((item) => item.guideline_id)).toEqual(['a', 'b'])
    expect(state.nextOffset).toBe(2)
    expect(state.hasMore).toBe(true)
  })

  it('не дублирует клинрек, пришедший на двух страницах', () => {
    const first = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)
    const second = mergePage(first, [guideline('b'), guideline('c')], PAGE_SIZE)

    expect(second.items.map((item) => item.guideline_id)).toEqual(['a', 'b', 'c'])
    expect(second.nextOffset).toBe(4)
  })

  it('считает список исчерпанным после короткой страницы', () => {
    const state = mergePage(initialListState(null), [guideline('a')], PAGE_SIZE)

    expect(state.hasMore).toBe(false)
    expect(state.nextOffset).toBe(1)
  })

  it('пустая страница завершает список', () => {
    const state = mergePage(initialListState(null), [], PAGE_SIZE)

    expect(state.items).toEqual([])
    expect(state.hasMore).toBe(false)
  })
})

describe('applyFilter', () => {
  it('сбрасывает накопленные страницы при смене фильтра', () => {
    const loaded = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)
    const filtered = applyFilter(loaded, 'ready')

    expect(filtered.items).toEqual([])
    expect(filtered.nextOffset).toBe(0)
    expect(filtered.status).toBe('ready')
  })

  it('сохраняет состояние, если фильтр не изменился', () => {
    const loaded = mergePage(initialListState('ready'), [guideline('a')], PAGE_SIZE)

    expect(applyFilter(loaded, 'ready')).toBe(loaded)
  })
})

describe('nextPagePath', () => {
  it('первый запрос идёт с нуля', () => {
    expect(nextPagePath(initialListState(null), PAGE_SIZE)).toBe('/api/guidelines?limit=2&offset=0')
  })

  it('фильтр попадает в запрос', () => {
    expect(nextPagePath(initialListState('uploaded'), PAGE_SIZE)).toBe(
      '/api/guidelines?status=uploaded&limit=2&offset=0',
    )
  })

  it('догрузка увеличивает смещение', () => {
    const loaded = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)

    expect(nextPagePath(loaded, PAGE_SIZE)).toBe('/api/guidelines?limit=2&offset=2')
  })
})
