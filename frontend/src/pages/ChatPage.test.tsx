// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../App'
import type { ChatAnswer } from '../api/chat'
import type { Guideline } from '../api/guidelines'
import { ChatSessionProvider } from '../store/chatSession'
import { ChatPage } from './ChatPage'

const GUIDELINE_ID = '7434ecc7-58ec-4925-9b93-cb4d507646ca'
const CHUNK_ID = '4f1d6e2a-1111-4222-8333-944455556666'
const QUESTION = 'до какого давления снижать пациенту 60 лет?'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const GUIDELINE: Guideline = {
  guideline_id: GUIDELINE_ID,
  version: 1,
  title: 'Гипертензия',
  filename: 'kr62.pdf',
  size_bytes: 1024,
  sha256: '0'.repeat(64),
  status: 'ready',
  created_at: '2026-10-21T18:43:09Z',
  error: null,
  icd_codes: ['I10'],
  chunks_total: 427,
  chunks_indexed: 427,
  embedding_model: 'Qwen/Qwen3-Embedding-0.6B',
  indexed_at: '2026-10-21T18:46:31Z',
}

function answered(): ChatAnswer {
  return {
    status: 'answered',
    answer: 'Снижать до 140/90 [1].',
    citations: [
      {
        n: 1,
        chunk_id: CHUNK_ID,
        guideline_id: GUIDELINE_ID,
        guideline_version: 1,
        guideline_title: 'Гипертензия',
        section: '3.2. Целевые уровни',
        page: 9,
        quote: 'Целевой уровень АД — ниже 140/90 мм рт. ст.',
      },
    ],
    search: { expression: 'целевой уровень АД', rewritten: true, constraints_lost: 0 },
    searched_guidelines: [{ guideline_id: GUIDELINE_ID, title: 'Гипертензия', version: 1 }],
  }
}

function notFound(): ChatAnswer {
  return { ...answered(), status: 'not_found', answer: null, citations: [] }
}

/** Подменить сеть: список документов и ответ чата. */
function stubApi(ask: () => ChatAnswer | { status: number; detail: string }) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.startsWith('/api/guidelines')) {
      return new Response(JSON.stringify([GUIDELINE]), { status: 200 })
    }
    const result = ask()
    if ('status' in result && typeof result.status === 'number') {
      return new Response(JSON.stringify({ detail: result.detail }), { status: result.status })
    }
    return new Response(JSON.stringify(result), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPage(path = `/chat?docs=${GUIDELINE_ID}`) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ChatSessionProvider>
        <ChatPage />
      </ChatSessionProvider>
    </MemoryRouter>,
  )
}

/** Приложение целиком: нужно, чтобы проверить переходы между разделами. */
function renderApp(path = `/chat?docs=${GUIDELINE_ID}`) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('ChatPage', () => {
  it('без выбранных документов не даёт отправить вопрос', async () => {
    stubApi(answered)
    renderPage('/chat')

    const send = await screen.findByRole('button', { name: 'Отправить' })

    expect((send as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('Сначала выберите хотя бы один документ')).toBeTruthy()
  })

  it('показывает пустую ленту с подсказками', async () => {
    stubApi(answered)
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Спросите клинические рекомендации' })).toBeTruthy()
    expect(
      screen.getByRole('button', { name: /Какие препараты первой линии/ }),
    ).toBeTruthy()
  })

  it('подставляет подсказку в поле вопроса', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderPage()

    await user.click(await screen.findByRole('button', { name: /До какого давления снижать/ }))

    const field = screen.getByLabelText('Вопрос по клинрекам') as HTMLTextAreaElement
    expect(field.value).toContain('До какого давления')
  })

  it('отправляет вопрос и показывает пару реплик', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(answered)
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText(/Снижать до 140\/90/)).toBeTruthy()
    expect(screen.getByText(QUESTION)).toBeTruthy()
    const askCall = fetchMock.mock.calls.at(-1)
    expect(String(askCall?.[0])).toBe('/api/chat/ask')
  })

  it('Enter отправляет вопрос, Shift+Enter — нет', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(answered)
    renderPage()

    const field = await screen.findByLabelText('Вопрос по клинрекам')
    await user.type(field, QUESTION)
    await user.keyboard('{Shift>}{Enter}{/Shift}')

    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/chat/ask')).toBe(false)

    await user.keyboard('{Enter}')

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/chat/ask')).toBe(true),
    )
  })

  it('ведёт по маркеру в просмотрщик на фрагмент', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    const marker = await screen.findByRole('link', { name: 'Источник 1' })

    expect(marker.getAttribute('href')).toBe(`/library/${GUIDELINE_ID}/view?chunk=${CHUNK_ID}`)
  })

  it('показывает источник с цитатой и страницей', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    const source = await screen.findByRole('link', {
      name: /\[1\] Гипертензия, 3.2. Целевые уровни, стр. 9/,
    })
    expect(source.getAttribute('href')).toBe(`/library/${GUIDELINE_ID}/view?chunk=${CHUNK_ID}`)
    expect(screen.getByText('Целевой уровень АД — ниже 140/90 мм рт. ст.')).toBeTruthy()
  })

  it('показывает отказ как отсутствие ответа, а не как сбой', async () => {
    const user = userEvent.setup()
    stubApi(notFound)
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText('В выбранных документах нет ответа')).toBeTruthy()
  })

  it('показывает прозрачность поиска: документы и формулировку запроса', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText(/Поиск:/)).toBeTruthy()
    expect(screen.getByText('целевой уровень АД')).toBeTruthy()
  })

  it('ошибку сервера показывает с возможностью повторить', async () => {
    const user = userEvent.setup()
    stubApi(() => ({ status: 502, detail: 'GigaChat request failed' }))
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText('Не удалось получить ответ')).toBeTruthy()
    expect(screen.getByText('GigaChat request failed')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeTruthy()
  })

  it('рисует markdown-ответ списком, а не одной строкой', async () => {
    const user = userEvent.setup()
    stubApi(() => ({
      ...answered(),
      answer: 'Выбор зависит от ситуации:\n\n- комбинация при АГ 2 степени [1]\n- моксонидин при метаболических нарушениях',
    }))
    renderPage()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText('моксонидин при метаболических нарушениях')).toBeTruthy()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(2)
  })

  it('лента переживает переход в библиотеку и обратно', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderApp()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    await screen.findByText(/Снижать до 140\/90/)

    await user.click(screen.getByRole('link', { name: 'Библиотека' }))
    await screen.findByText('Клинические рекомендации')
    await user.click(screen.getByRole('link', { name: 'Чат' }))

    expect(await screen.findByText(QUESTION)).toBeTruthy()
    expect(screen.getByText(/Снижать до 140\/90/)).toBeTruthy()
  })

  it('после перезагрузки страницы лента пуста', async () => {
    stubApi(answered)
    const first = renderApp()
    await screen.findByText('Спросите клинические рекомендации')
    first.unmount()

    renderApp()

    // Новый провайдер сессии — новый разговор: прошлых реплик нет
    expect(await screen.findByText('Спросите клинические рекомендации')).toBeTruthy()
    expect(screen.queryByText(QUESTION)).toBeNull()
  })

  it('«Новый чат» очищает ленту', async () => {
    const user = userEvent.setup()
    stubApi(answered)
    renderApp()

    await user.type(await screen.findByLabelText('Вопрос по клинрекам'), QUESTION)
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    await screen.findByText(/Снижать до 140\/90/)

    await user.click(screen.getByRole('button', { name: 'Новый чат' }))

    expect(screen.queryByText(QUESTION)).toBeNull()
    expect(screen.getByText('Спросите клинические рекомендации')).toBeTruthy()
  })
})
