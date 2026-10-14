import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { Guideline } from '../api/guidelines'
import { GuidelineRow } from './GuidelineRow'

const GUIDELINE: Guideline = {
  guideline_id: '5fc51635-7cdf-4efe-99dd-fa7028434376',
  version: 1,
  title: 'Гипертензия',
  filename: 'КР62_3.pdf',
  size_bytes: 3_202_485,
  sha256: 'b10d1f1df988056b5be83380e9be72ca4af6056deecfa93dd06dc84ca1e2afe3',
  status: 'uploaded',
  created_at: '2026-10-08T15:54:15.575244Z',
  error: null,
}

/**
 * Текст строки без разметки.
 *
 * `react-dom/server` вставляет `<!-- -->` между текстовыми узлами, чтобы работала гидратация;
 * для проверок содержимого эти маркеры только мешают.
 */
function render(guideline: Guideline): string {
  return renderToString(
    <MemoryRouter>
      <ul>
        <GuidelineRow guideline={guideline} />
      </ul>
    </MemoryRouter>,
  ).replace(/<!--.*?-->/g, '')
}

describe('GuidelineRow', () => {
  it('показывает название, файл, размер, дату и версию', () => {
    const html = render(GUIDELINE)

    expect(html).toContain('Гипертензия')
    expect(html).toContain('КР62_3.pdf')
    expect(html).toContain('3,1 МБ')
    expect(html).toContain('версия 1')
    expect(html).toMatch(/\d{2}\.\d{2}\.\d{4}/)
  })

  it('ведёт в просмотрщик этого клинрека', () => {
    expect(render(GUIDELINE)).toContain(
      'href="/library/5fc51635-7cdf-4efe-99dd-fa7028434376/view"',
    )
  })

  it('показывает статус из ответа сервера, не выдавая загруженный за готовый', () => {
    const html = render(GUIDELINE)

    expect(html).toContain('Загружен')
    expect(html).not.toContain('Готов к проверке')
  })

  it('показывает причину падения при статусе failed', () => {
    const html = render({ ...GUIDELINE, status: 'failed', error: 'pdf parsing failed' })

    expect(html).toContain('Ошибка обработки')
    expect(html).toContain('pdf parsing failed')
  })
})
