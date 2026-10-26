import { describe, expect, it } from 'vitest'

import type { Guideline } from '../api/guidelines'
import {
  describeProgress,
  describeVectorization,
  indexingPercent,
  isFinalStatus,
  needsPolling,
  needsPollingList,
} from './indexingStatus'

function guideline(overrides: Partial<Guideline> = {}): Guideline {
  return {
    guideline_id: '5fc51635-7cdf-4efe-99dd-fa7028434376',
    version: 1,
    title: 'Гипертензия',
    filename: 'КР62_3.pdf',
    size_bytes: 1024,
    sha256: 'a'.repeat(64),
    status: 'uploaded',
    created_at: '2026-10-14T10:00:00Z',
    error: null,
    chunks_total: null,
    chunks_indexed: null,
    embedding_model: null,
    indexed_at: null,
    ...overrides,
  }
}

describe('isFinalStatus', () => {
  it('считает окончательными ready и failed', () => {
    expect(isFinalStatus('ready')).toBe(true)
    expect(isFinalStatus('failed')).toBe(true)
  })

  it('не считает окончательными uploaded и processing', () => {
    expect(isFinalStatus('uploaded')).toBe(false)
    expect(isFinalStatus('processing')).toBe(false)
  })
})

describe('needsPollingList', () => {
  it('опрашивает список, пока есть незавершённые клинреки', () => {
    expect(needsPollingList([guideline({ status: 'ready' }), guideline({ status: 'processing' })])).toBe(
      true,
    )
    expect(needsPolling(guideline({ status: 'uploaded' }))).toBe(true)
  })

  it('останавливает опрос, когда все статусы окончательные', () => {
    expect(
      needsPollingList([guideline({ status: 'ready' }), guideline({ status: 'failed' })]),
    ).toBe(false)
  })

  it('не опрашивает пустой список', () => {
    expect(needsPollingList([])).toBe(false)
  })
})

describe('describeProgress', () => {
  it('показывает ход обработки, когда известно общее число фрагментов', () => {
    const text = describeProgress(
      guideline({ status: 'processing', chunks_total: 434, chunks_indexed: 120 }),
    )

    expect(text).toBe('Обработано 120 из 434 фрагментов')
  })

  it('показывает начало обработки, пока фрагменты не посчитаны', () => {
    expect(describeProgress(guideline({ status: 'processing' }))).toBe(
      'Обработка идёт: документ читается',
    )
  })

  it('молчит для остальных статусов', () => {
    expect(describeProgress(guideline({ status: 'uploaded' }))).toBeNull()
    expect(describeProgress(guideline({ status: 'ready' }))).toBeNull()
  })
})

describe('describeVectorization', () => {
  it('показывает признак векторизации с числом фрагментов и моделью', () => {
    const text = describeVectorization(
      guideline({
        status: 'ready',
        chunks_total: 434,
        embedding_model: 'Qwen/Qwen3-Embedding-0.6B',
      }),
    )

    expect(text).toBe('Векторизован · 434 фрагментов · Qwen/Qwen3-Embedding-0.6B')
  })

  it('не показывает признак, пока клинрек не готов', () => {
    expect(describeVectorization(guideline({ status: 'processing', chunks_total: 10 }))).toBeNull()
    expect(describeVectorization(guideline({ status: 'failed' }))).toBeNull()
    expect(describeVectorization(guideline({ status: 'uploaded' }))).toBeNull()
  })
})

describe('indexingPercent', () => {
  it('считает долю обработанных фрагментов', () => {
    expect(
      indexingPercent(
        guideline({ status: 'processing', chunks_total: 120, chunks_indexed: 34 }),
      ),
    ).toBe(28)
  })

  it('не выходит за границы, даже если сервер прислал больше обработанных', () => {
    expect(
      indexingPercent(guideline({ status: 'processing', chunks_total: 10, chunks_indexed: 50 })),
    ).toBe(100)
  })

  it('не показывает полосу без общего числа фрагментов', () => {
    expect(
      indexingPercent(guideline({ status: 'processing', chunks_total: null })),
    ).toBeNull()
    expect(indexingPercent(guideline({ status: 'processing', chunks_total: 0 }))).toBeNull()
  })

  it('не показывает полосу для окончательных статусов', () => {
    expect(
      indexingPercent(guideline({ status: 'ready', chunks_total: 10, chunks_indexed: 10 })),
    ).toBeNull()
  })
})
