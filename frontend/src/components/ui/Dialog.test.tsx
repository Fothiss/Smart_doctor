// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { Button } from './Button'
import { Dialog } from './Dialog'

afterEach(cleanup)

/** Диалог, который открывается действием пользователя: только тогда Radix возвращает фокус. */
function Harness({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <Button onClick={() => setOpen(true)}>Удалить</Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Удалить клинрек?"
        description="Действие необратимо"
      >
        <Button
          variant="danger"
          onClick={() => {
            onConfirm()
            setOpen(false)
          }}
        >
          Подтвердить
        </Button>
        <Button onClick={() => setOpen(false)}>Отмена</Button>
      </Dialog>
    </>
  )
}

describe('Dialog', () => {
  it('открывается и показывает заголовок с описанием', async () => {
    const user = userEvent.setup()
    render(<Harness onConfirm={() => {}} />)

    await user.click(screen.getByRole('button', { name: 'Удалить' }))

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('Удалить клинрек?')).toBeTruthy()
    expect(screen.getByText('Действие необратимо')).toBeTruthy()
  })

  it('закрывается по Esc без выполнения действия и возвращает фокус', async () => {
    const user = userEvent.setup()
    let confirmed = false
    render(<Harness onConfirm={() => (confirmed = true)} />)

    const trigger = screen.getByRole('button', { name: 'Удалить' })
    await user.click(trigger)
    await user.keyboard('{Escape}')

    expect(confirmed).toBe(false)
    expect(screen.queryByRole('dialog')).toBeNull()
    // Radix возвращает фокус отложенно: проверяем, дождавшись кадра
    await waitFor(() => expect(document.activeElement).toBe(trigger))
  })

  it('выполняет подтверждённое действие', async () => {
    const user = userEvent.setup()
    let confirmed = false
    render(<Harness onConfirm={() => (confirmed = true)} />)

    await user.click(screen.getByRole('button', { name: 'Удалить' }))
    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))

    expect(confirmed).toBe(true)
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
