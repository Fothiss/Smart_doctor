// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MultiCombobox, type MultiComboboxItem } from './MultiCombobox'

afterEach(cleanup)

const ITEMS: MultiComboboxItem[] = [
  { value: 'a', label: 'Гипертензия · I10' },
  { value: 'b', label: 'ХБП · N18' },
  { value: 'c', label: 'Подагра · M10' },
]

function renderPicker(values: string[], limit = 5) {
  const onChange = vi.fn()
  render(
    <MultiCombobox
      items={ITEMS}
      values={values}
      onChange={onChange}
      label="Документы"
      limit={limit}
    />,
  )
  return onChange
}

describe('MultiCombobox', () => {
  it('без выбора показывает подсказку', () => {
    renderPicker([])

    expect(screen.getByRole('button', { name: 'Документы' }).textContent).toBe(
      'Выберите документы',
    )
  })

  it('показывает выбранные документы чипами', () => {
    renderPicker(['a'])

    expect(screen.getByText('Гипертензия · I10')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Убрать Гипертензия · I10' })).toBeTruthy()
  })

  it('добавляет документ по клику и не закрывает список', async () => {
    const user = userEvent.setup()
    const onChange = renderPicker([])

    await user.click(screen.getByRole('button', { name: 'Документы' }))
    await user.click(screen.getByRole('option', { name: 'ХБП · N18' }))

    expect(onChange).toHaveBeenCalledWith(['b'])
    expect(screen.getByRole('listbox', { name: 'Документы' })).toBeTruthy()
  })

  it('снимает выбор повторным кликом', async () => {
    const user = userEvent.setup()
    const onChange = renderPicker(['a'])

    await user.click(screen.getByRole('button', { name: 'Документы' }))
    await user.click(screen.getByRole('option', { selected: true, name: 'Гипертензия · I10' }))

    expect(onChange).toHaveBeenCalledWith([])
  })

  it('ищет по подписи и не показывает лишнего', async () => {
    const user = userEvent.setup()
    renderPicker([])

    await user.click(screen.getByRole('button', { name: 'Документы' }))
    await user.type(screen.getByRole('textbox', { name: /Поиск/ }), 'N18')

    expect(screen.getAllByRole('option')).toHaveLength(1)
    expect(screen.getByRole('option', { name: 'ХБП · N18' })).toBeTruthy()
  })

  it('упирается в предел выбора и сообщает об этом', async () => {
    const user = userEvent.setup()
    const onChange = renderPicker(['a', 'b'], 2)

    await user.click(screen.getByRole('button', { name: 'Документы' }))
    await user.click(screen.getByRole('option', { name: 'Подагра · M10' }))

    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByRole('status').textContent).toBe('Больше документов выбрать нельзя')
  })

  it('убирает выбранное кнопкой в чипе', async () => {
    const user = userEvent.setup()
    const onChange = renderPicker(['a', 'b'])

    await user.click(screen.getByRole('button', { name: 'Убрать ХБП · N18' }))

    expect(onChange).toHaveBeenCalledWith(['a'])
  })
})
