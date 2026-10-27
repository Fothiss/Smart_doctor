// @vitest-environment jsdom
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ChatAnswer } from '../api/chat'
import { ChatSessionProvider, useChatSession } from './chatSession'

const ANSWER: ChatAnswer = {
  status: 'answered',
  answer: 'ответ [1]',
  citations: [],
  search: { expression: 'тезис', rewritten: true, constraints_lost: 0 },
  searched_guidelines: [],
}

afterEach(cleanup)

/** Пробник: показывает текущее состояние сессии и даёт кнопки действий. */
function Probe() {
  const session = useChatSession()
  return (
    <div>
      <p data-testid="count">{session.entries.length}</p>
      <p data-testid="draft">{session.draft}</p>
      <p data-testid="last">{session.entries.at(-1)?.question ?? '—'}</p>
      <button
        type="button"
        onClick={() => session.append({ question: 'вопрос', answer: ANSWER })}
      >
        добавить
      </button>
      <button type="button" onClick={() => session.setDraft('черновик')}>
        черновик
      </button>
      <button type="button" onClick={session.reset}>
        сброс
      </button>
    </div>
  )
}

function renderProbe() {
  return render(
    <ChatSessionProvider>
      <Probe />
    </ChatSessionProvider>,
  )
}

describe('ChatSessionProvider', () => {
  it('добавляет реплики по порядку', () => {
    renderProbe()

    act(() => {
      screen.getByRole('button', { name: 'добавить' }).click()
      screen.getByRole('button', { name: 'добавить' }).click()
    })

    expect(screen.getByTestId('count').textContent).toBe('2')
    expect(screen.getByTestId('last').textContent).toBe('вопрос')
  })

  it('хранит черновик вопроса', () => {
    renderProbe()

    act(() => {
      screen.getByRole('button', { name: 'черновик' }).click()
    })

    expect(screen.getByTestId('draft').textContent).toBe('черновик')
  })

  it('сброс очищает и ленту, и черновик', () => {
    renderProbe()
    act(() => {
      screen.getByRole('button', { name: 'добавить' }).click()
      screen.getByRole('button', { name: 'черновик' }).click()
      screen.getByRole('button', { name: 'сброс' }).click()
    })

    expect(screen.getByTestId('count').textContent).toBe('0')
    expect(screen.getByTestId('draft').textContent).toBe('')
  })

  it('вне провайдера — ошибка конфигурации', () => {
    expect(() => render(<Probe />)).toThrow(/ChatSessionProvider/)
  })
})
