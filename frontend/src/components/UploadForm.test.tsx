import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { UploadForm } from './UploadForm'

/** Разметка формы загрузки без маркеров гидратации. */
function render(): string {
  return renderToString(
    <MemoryRouter>
      <UploadForm onUploaded={() => {}} />
    </MemoryRouter>,
  ).replace(/<!--.*?-->/g, '')
}

describe('UploadForm', () => {
  it('требует коды МКБ и показывает подсказку формата', () => {
    const html = render()

    expect(html).toContain('Коды МКБ-10')
    expect(html).toContain('например I10 или I10.1')
  })

  it('не даёт отправить форму без файла и кодов', () => {
    const html = render()

    expect(html).toContain('disabled')
    expect(html).toContain('Загрузить')
  })
})
