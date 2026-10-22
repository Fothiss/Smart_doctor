import { describe, expect, it } from 'vitest'

import { ApiError } from '../api/client'
import {
  IDLE_DELETE,
  cancelDelete,
  deleteErrorFor,
  deletePhaseFor,
  describeDeleteError,
  failDelete,
  hideGuideline,
  requestDelete,
  startDelete,
} from './deleteGuideline'

const ID = '5fc51635-7cdf-4efe-99dd-fa7028434376'
const OTHER = 'a1dbc8bb-09e8-4db5-be74-ad2d19d34bf7'

describe('фазы удаления', () => {
  it('запрос удаления спрашивает подтверждение, а не удаляет сразу', () => {
    const state = requestDelete(IDLE_DELETE, ID)

    expect(state).toEqual({ kind: 'confirming', guidelineId: ID })
    expect(deletePhaseFor(state, ID)).toBe('confirming')
  })

  it('подтверждение переводит в выполнение', () => {
    const state = startDelete(requestDelete(IDLE_DELETE, ID))

    expect(state).toEqual({ kind: 'deleting', guidelineId: ID })
  })

  it('без подтверждения выполнение не начинается', () => {
    expect(startDelete(IDLE_DELETE)).toBe(IDLE_DELETE)
  })

  it('отмена возвращает в исходное состояние', () => {
    expect(cancelDelete(requestDelete(IDLE_DELETE, ID))).toBe(IDLE_DELETE)
  })

  it('во время выполнения отмена не действует — запрос уже ушёл', () => {
    const deleting = startDelete(requestDelete(IDLE_DELETE, ID))

    expect(cancelDelete(deleting)).toBe(deleting)
  })

  it('фаза относится только к своей строке', () => {
    const state = requestDelete(IDLE_DELETE, ID)

    expect(deletePhaseFor(state, ID)).toBe('confirming')
    expect(deletePhaseFor(state, OTHER)).toBe('idle')
  })

  it('отказ записывается для той же строки и не мешает остальным', () => {
    const state = failDelete(startDelete(requestDelete(IDLE_DELETE, ID)), new ApiError(409, 'busy'))

    expect(state.kind).toBe('error')
    expect(deletePhaseFor(state, ID)).toBe('error')
    expect(deleteErrorFor(state, ID)).toContain('индексация')
    expect(deleteErrorFor(state, OTHER)).toBeNull()
  })

  it('без активного удаления отказ ничего не меняет', () => {
    expect(failDelete(IDLE_DELETE, new ApiError(503, 'down'))).toBe(IDLE_DELETE)
  })
})

describe('describeDeleteError', () => {
  it('объясняет коды ответов словами', () => {
    expect(describeDeleteError(new ApiError(404, 'not found'))).toContain('уже удалён')
    expect(describeDeleteError(new ApiError(409, 'busy'))).toContain('индексация')
    expect(describeDeleteError(new ApiError(503, 'down'))).toContain('Векторное хранилище')
  })

  it('неизвестную ошибку показывает как есть', () => {
    expect(describeDeleteError(new ApiError(500, 'internal'))).toBe('internal')
    expect(describeDeleteError('не ошибка')).toBe('Неизвестная ошибка')
  })
})

describe('hideGuideline', () => {
  it('добавляет идентификатор один раз', () => {
    expect(hideGuideline([], ID)).toEqual([ID])
    expect(hideGuideline([ID], ID)).toEqual([ID])
    expect(hideGuideline([ID], OTHER)).toEqual([ID, OTHER])
  })
})
