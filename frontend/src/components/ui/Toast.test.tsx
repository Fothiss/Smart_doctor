// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider, useToast } from './Toast'

afterEach(cleanup)

/** Кнопка, которая сообщает результат действия. */
function DeleteButton({ tone }: { tone?: 'success' | 'error' }) {
  const notify = useToast()

  return (
    <button onClick={() => notify({ title: 'Клинрек удалён', tone })} type="button">
      Удалить
    </button>
  )
}

describe('Toast', () => {
  it('объявляет результат как статусное сообщение', async () => {
    render(
      <ToastProvider>
        <DeleteButton />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Удалить' }))

    const title = await screen.findByText('Клинрек удалён')
    const liveRegion = title.closest('[role="status"]')

    expect(liveRegion).not.toBeNull()
    expect(liveRegion?.getAttribute('aria-live')).toBe('polite')
  })

  it('исчезает сам по таймеру', async () => {
    // Короткое время показа вместо подмены таймеров: так проверяется настоящее поведение
    render(
      <ToastProvider duration={30}>
        <DeleteButton />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Удалить' }))
    expect(screen.getByText('Клинрек удалён')).toBeTruthy()

    await waitFor(() => expect(screen.queryByText('Клинрек удалён')).toBeNull(), {
      timeout: 2000,
    })
  })

  it('требует провайдера: без него уведомление некуда послать', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => render(<DeleteButton />)).toThrow('useToast must be used inside ToastProvider')

    consoleError.mockRestore()
  })
})
