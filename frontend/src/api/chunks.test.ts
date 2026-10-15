import { describe, expect, it, vi } from 'vitest'

import { ApiError, apiErrorFromResponse } from './client'
import { chunkPath, getChunk, guidelineIndexPath, indexGuideline } from './guidelines'

describe('chunkPath', () => {
  it('собирает адрес фрагмента', () => {
    expect(chunkPath('5c1f7a90-2b4d-4f6e-9a11-8d3c0e5b7f42')).toBe(
      '/api/chunks/5c1f7a90-2b4d-4f6e-9a11-8d3c0e5b7f42',
    )
  })

  it('кодирует идентификатор', () => {
    expect(chunkPath('a/b c')).toBe('/api/chunks/a%2Fb%20c')
  })
})

describe('guidelineIndexPath', () => {
  it('собирает адрес повторной индексации', () => {
    expect(guidelineIndexPath('abc')).toBe('/api/guidelines/abc/index')
  })
})

describe('getChunk', () => {
  it('возвращает разобранный фрагмент', async () => {
    const chunk = { chunk_id: 'x', text: 'цитата', rects: [] }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(chunk), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getChunk('x')).resolves.toEqual(chunk)
    expect(fetchMock).toHaveBeenCalledWith('/api/chunks/x', expect.anything())

    vi.unstubAllGlobals()
  })

  it('разбирает 404 в понятную ошибку', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'chunk not found' }), { status: 404 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getChunk('x')).rejects.toThrow('chunk not found')

    vi.unstubAllGlobals()
  })
})

describe('indexGuideline', () => {
  it('отправляет POST на адрес индексации', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ guideline_id: 'abc', status: 'processing' }), { status: 202 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await indexGuideline('abc')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/guidelines/abc/index',
      expect.objectContaining({ method: 'POST' }),
    )

    vi.unstubAllGlobals()
  })

  it('показывает причину конфликта', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'indexing is already running for guideline abc' }), {
        status: 409,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(indexGuideline('abc')).rejects.toBeInstanceOf(ApiError)

    vi.unstubAllGlobals()
  })
})

describe('apiErrorFromResponse', () => {
  it('достаёт сообщение из строкового detail', () => {
    expect(apiErrorFromResponse(503, '{"detail":"vector store is unavailable"}').message).toBe(
      'vector store is unavailable',
    )
  })
})
