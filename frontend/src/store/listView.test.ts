import { describe, expect, it } from 'vitest'

import { selectListView } from './listView'

describe('selectListView', () => {
  it('во время загрузки показывает индикатор', () => {
    expect(selectListView({ isLoading: true, error: null, count: 0, status: null })).toEqual({
      kind: 'loading',
    })
  })

  it('загрузка важнее уже показанной ошибки', () => {
    expect(
      selectListView({ isLoading: true, error: 'было', count: 0, status: null }).kind,
    ).toBe('loading')
  })

  it('ошибка списка показывается как ошибка, а не как пустота', () => {
    expect(
      selectListView({ isLoading: false, error: 'Сервер недоступен', count: 0, status: null }),
    ).toEqual({ kind: 'error', message: 'Сервер недоступен' })
  })

  it('пустое хранилище отличается от пустого результата фильтра', () => {
    expect(selectListView({ isLoading: false, error: null, count: 0, status: null })).toEqual({
      kind: 'empty',
      filtered: false,
    })
    expect(selectListView({ isLoading: false, error: null, count: 0, status: 'ready' })).toEqual({
      kind: 'empty',
      filtered: true,
    })
  })

  it('непустой список показывается списком', () => {
    expect(selectListView({ isLoading: false, error: null, count: 3, status: 'ready' }).kind).toBe(
      'list',
    )
  })

  it('фильтр по коду МКБ делает пустой результат отфильтрованным', () => {
    expect(
      selectListView({ isLoading: false, error: null, count: 0, status: null, icd: 'I10' }),
    ).toEqual({ kind: 'empty', filtered: true })
    expect(
      selectListView({ isLoading: false, error: null, count: 0, status: null, icd: null }),
    ).toEqual({ kind: 'empty', filtered: false })
  })
})
