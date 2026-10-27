import { afterEach, describe, expect, it, vi } from 'vitest'

import { askChat } from './chat'
import { ApiError } from './client'

const GUIDELINE_ID = '7434ecc7-58ec-4925-9b93-cb4d507646ca'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(response: { status: number; body: string }) {
  const fetchMock = vi.fn(async () => new Response(response.body, { status: response.status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('askChat', () => {
  it('отправляет вопрос на сервер и возвращает разобранный ответ', async () => {
    const fetchMock = stubFetch({
      status: 200,
      body: JSON.stringify({
        status: 'answered',
        answer: 'ответ [1]',
        citations: [],
        search: { expression: 'тезис', rewritten: true, constraints_lost: 0 },
        searched_guidelines: [],
      }),
    })

    const answer = await askChat({ guideline_ids: [GUIDELINE_ID], question: 'вопрос' })

    expect(answer.status).toBe('answered')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(path).toBe('/api/chat/ask')
    expect(JSON.parse(String(init.body))).toMatchObject({ question: 'вопрос' })
  })

  it('отказ модели превращается в читаемую ошибку', async () => {
    stubFetch({ status: 502, body: JSON.stringify({ detail: 'GigaChat request failed' }) })

    await expect(askChat({ guideline_ids: [GUIDELINE_ID], question: 'вопрос' })).rejects.toThrow(
      new ApiError(502, 'GigaChat request failed'),
    )
  })
})
