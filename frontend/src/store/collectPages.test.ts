import { describe, expect, it } from 'vitest'

import type { Guideline, GuidelineStatus } from '../api/guidelines'
import { type FetchPage, collectPages, loadNextPage } from './collectPages'
import { initialListState, mergePage } from './guidelineList'

const PAGE_SIZE = 2

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

type Call = { status: GuidelineStatus | null; limit: number; offset: number }

/** Подмена сети: отдаёт заранее заданные страницы и записывает параметры запросов. */
function stubFetch(pages: readonly (readonly Guideline[])[]): { fetchPage: FetchPage; calls: Call[] } {
  const calls: Call[] = []
  const fetchPage: FetchPage = (params) => {
    calls.push(params)
    return Promise.resolve([...(pages[calls.length - 1] ?? [])])
  }
  return { fetchPage, calls }
}

describe('collectPages', () => {
  it('первый запрос идёт с нуля и с размером страницы', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('a')]])

    await collectPages(fetchPage, null, 0, PAGE_SIZE)

    expect(calls).toEqual([{ status: null, limit: PAGE_SIZE, offset: 0 }])
  })

  it('фильтр попадает в каждый запрос', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('a'), guideline('b')], [guideline('c')]])

    await collectPages(fetchPage, 'ready', PAGE_SIZE, PAGE_SIZE)

    expect(calls).toHaveLength(2)
    expect(calls[0]?.status).toBe('ready')
    expect(calls[1]?.status).toBe('ready')
  })

  it('догрузка увеличивает смещение на размер страницы', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('a'), guideline('b')], [guideline('c')]])

    const state = await collectPages(fetchPage, null, PAGE_SIZE, PAGE_SIZE)

    expect(calls.map((call) => call.offset)).toEqual([0, PAGE_SIZE])
    expect(state.items).toHaveLength(3)
  })

  it('останавливается на короткой странице, не запрашивая лишнего', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('a')]])

    const state = await collectPages(fetchPage, null, PAGE_SIZE * 5, PAGE_SIZE)

    expect(calls).toHaveLength(1)
    expect(state.hasMore).toBe(false)
  })

  it('восстанавливает позицию из адреса', async () => {
    const { fetchPage, calls } = stubFetch([
      [guideline('a'), guideline('b')],
      [guideline('c'), guideline('d')],
      [guideline('e')],
    ])

    const state = await collectPages(fetchPage, null, PAGE_SIZE * 2, PAGE_SIZE)

    expect(calls.map((call) => call.offset)).toEqual([0, PAGE_SIZE, PAGE_SIZE * 2])
    expect(state.items.map((item) => item.guideline_id)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  it('пустая первая страница даёт пустой список без ошибки', async () => {
    const { fetchPage } = stubFetch([[]])

    const state = await collectPages(fetchPage, null, 0, PAGE_SIZE)

    expect(state.items).toEqual([])
    expect(state.hasMore).toBe(false)
  })
})

describe('loadNextPage', () => {
  it('запрашивает следующую страницу по текущему смещению', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('c'), guideline('d')]])
    const loaded = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)

    const state = await loadNextPage(fetchPage, loaded, PAGE_SIZE)

    expect(calls).toEqual([{ status: null, limit: PAGE_SIZE, offset: PAGE_SIZE }])
    expect(state.items.map((item) => item.guideline_id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('не дублирует клинрек, вернувшийся повторно', async () => {
    const { fetchPage } = stubFetch([[guideline('b'), guideline('c')]])
    const loaded = mergePage(initialListState(null), [guideline('a'), guideline('b')], PAGE_SIZE)

    const state = await loadNextPage(fetchPage, loaded, PAGE_SIZE)

    expect(state.items.map((item) => item.guideline_id)).toEqual(['a', 'b', 'c'])
  })

  it('сохраняет фильтр при догрузке', async () => {
    const { fetchPage, calls } = stubFetch([[guideline('c')]])
    const loaded = mergePage(initialListState('failed'), [guideline('a')], PAGE_SIZE)

    await loadNextPage(fetchPage, loaded, PAGE_SIZE)

    expect(calls[0]?.status).toBe('failed')
  })
})
