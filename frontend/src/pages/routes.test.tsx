import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppRoutes } from '../App'

/**
 * Дымовые проверки маршрутов без браузера.
 *
 * Рендер серверный: эффекты не выполняются, поэтому проверяется, что экран вообще
 * собирается и не падает. Перенаправление `/` → `/library` и работа в браузере
 * проверяются отдельно.
 */
function renderAt(path: string): string {
  return renderToString(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

describe('маршруты', () => {
  it('библиотека открывается и показывает состояние загрузки', () => {
    expect(renderAt('/library')).toContain('Библиотека клинреков')
  })

  it('просмотр клинрека открывается по идентификатору', () => {
    const html = renderAt('/library/5fc51635-7cdf-4efe-99dd-fa7028434376/view')

    expect(html).toContain('Клинрек')
    expect(html).toContain('В библиотеку')
  })

  it('просмотр принимает номер страницы в адресе', () => {
    expect(renderAt('/library/5fc51635-7cdf-4efe-99dd-fa7028434376/view?page=12')).toContain(
      'В библиотеку',
    )
  })

  it('неизвестный адрес даёт экран 404', () => {
    expect(renderAt('/no-such-page')).toContain('Страница не найдена')
  })

  it('корень рендерится без ошибок', () => {
    expect(() => renderAt('/')).not.toThrow()
  })

  it('фильтр из адреса читается без падения', () => {
    expect(renderAt('/library?status=uploaded&offset=50')).toContain('Библиотека клинреков')
    expect(renderAt('/library?status=мусор')).toContain('Библиотека клинреков')
  })
})
