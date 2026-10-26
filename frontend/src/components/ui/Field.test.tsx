// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import { Field } from './Field'

afterEach(cleanup)

/** Поле с проверкой на пустое значение: ошибка должна появляться и исчезать рядом с полем. */
function Harness() {
  const [value, setValue] = useState('')
  const empty = value.trim() === ''

  return (
    <Field
      id="icd"
      label="Код МКБ"
      hint="Формат: I10 или I10.1"
      error={empty ? 'Укажите код МКБ' : null}
    >
      {(props) => (
        <input {...props} value={value} onChange={(event) => setValue(event.target.value)} />
      )}
    </Field>
  )
}

describe('Field', () => {
  it('связывает подпись, подсказку и ошибку с полем', () => {
    render(<Harness />)

    const input = screen.getByLabelText('Код МКБ')

    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(input.getAttribute('aria-describedby')).toBe('icd-error icd-hint')
    expect(screen.getByText('Укажите код МКБ').getAttribute('id')).toBe('icd-error')
    expect(screen.getByText('Формат: I10 или I10.1').getAttribute('id')).toBe('icd-hint')
  })

  it('снимает ошибку при исправлении, сохраняя подсказку', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByLabelText('Код МКБ'), 'I10')

    const input = screen.getByLabelText('Код МКБ')
    expect(input.getAttribute('aria-invalid')).toBe('false')
    expect(input.getAttribute('aria-describedby')).toBe('icd-hint')
    expect(screen.queryByText('Укажите код МКБ')).toBeNull()
  })
})
