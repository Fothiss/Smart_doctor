// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { ProtocolPage } from './ProtocolPage'

afterEach(cleanup)

/** Экран вне роутера: без него не работают переходы, которые предлагает пустой выбор клинрека. */
function renderPage() {
  return render(
    <MemoryRouter>
      <ProtocolPage />
    </MemoryRouter>,
  )
}

describe('ProtocolPage', () => {
  it('показывает ошибки у своих полей до всякой отправки', async () => {
    renderPage()

    expect(await screen.findByText('Жалобы обязательны')).toBeTruthy()
    expect(screen.getByText('Код МКБ-10 обязателен')).toBeTruthy()
    expect(screen.getByText('Название диагноза обязательно')).toBeTruthy()
  })

  it('при отправке невалидной формы переводит фокус на первое невалидное поле', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: 'Проверить форму' }))

    await waitFor(() => expect(document.activeElement?.id).toBe('protocol-complaints'))
  })

  it('снимает ошибку поля, когда его заполнили', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Жалобы'), 'Головная боль')

    expect(screen.queryByText('Жалобы обязательны')).toBeNull()
    expect(screen.getByText('Код МКБ-10 обязателен')).toBeTruthy()
  })

  it('не отправляет форму и просит выбрать клинрек, когда поля в порядке', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Жалобы'), 'Головная боль')
    await user.type(screen.getByLabelText('Код МКБ-10'), 'I10')
    await user.type(screen.getByLabelText('Название диагноза'), 'Гипертензия')
    await user.click(screen.getByRole('button', { name: 'Проверить форму' }))

    expect(await screen.findByText('Выберите клинрек для проверки')).toBeTruthy()
  })
})
