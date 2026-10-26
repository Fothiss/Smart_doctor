// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { Combobox } from './Combobox'

afterEach(cleanup)

const ITEMS = [
  { value: 'hyper', label: 'Гипертоническая болезнь · I10' },
  { value: 'diabetes', label: 'Сахарный диабет 2 типа · E11' },
]

/** Выбор клинрека с выводом текущего значения. */
function Harness() {
  const [value, setValue] = useState<string | null>(null)

  return (
    <>
      <Combobox
        items={ITEMS}
        value={value}
        onChange={setValue}
        label="Клинрек"
        placeholder="Выберите клинрек"
      />
      <output data-testid="value">{value ?? 'пусто'}</output>
    </>
  )
}

describe('Combobox', () => {
  it('ищет по подстроке и выбирает Enter', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: /Выберите клинрек/ }))
    await user.type(screen.getByLabelText('Поиск'), 'диабет')

    expect(screen.getByRole('option', { name: /Сахарный диабет/ })).toBeTruthy()
    expect(screen.queryByRole('option', { name: /Гипертоническая/ })).toBeNull()

    await user.keyboard('{Enter}')

    expect(screen.getByTestId('value').textContent).toBe('diabetes')
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('выбирает стрелками', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: /Выберите клинрек/ }))
    await user.keyboard('{ArrowDown}{Enter}')

    expect(screen.getByTestId('value').textContent).toBe('diabetes')
  })

  it('Esc закрывает список без выбора', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const trigger = screen.getByRole('button', { name: /Выберите клинрек/ })
    await user.click(trigger)
    await user.keyboard('{Escape}')

    expect(screen.queryByRole('listbox')).toBeNull()
    expect(screen.getByTestId('value').textContent).toBe('пусто')
  })

  it('сообщает, когда совпадений нет, и не теряет выбранное значение', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: /Выберите клинрек/ }))
    await user.click(screen.getByRole('option', { name: /Сахарный диабет/ }))

    await user.click(screen.getByRole('button', { name: /Сахарный диабет/ }))
    await user.type(screen.getByLabelText('Поиск'), 'подагра')
    await user.keyboard('{Escape}')

    expect(screen.getByTestId('value').textContent).toBe('diabetes')
  })

  it('показывает текст об отсутствии совпадений', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: /Выберите клинрек/ }))
    await user.type(screen.getByLabelText('Поиск'), 'подагра')

    expect(screen.getByText('Ничего не найдено')).toBeTruthy()
    expect(screen.queryByRole('listbox')).toBeNull()
  })
})
