// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import type { Guideline } from '../api/guidelines'
import type { DeletePhase } from '../store/deleteGuideline'
import { GuidelineRow } from './GuidelineRow'

afterEach(cleanup)

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
  icd_codes: ['I10', 'I15'],
}

/**
 * Текст строки без разметки.
 *
 * `react-dom/server` вставляет `<!-- -->` между текстовыми узлами, чтобы работала гидратация;
 * для проверок содержимого эти маркеры только мешают.
 */
function renderToStringOf(
  guideline: Guideline,
  props: Partial<Parameters<typeof GuidelineRow>[0]> = {},
): string {
  return renderToString(
    <MemoryRouter>
      <ul>
        <GuidelineRow guideline={guideline} {...props} />
      </ul>
    </MemoryRouter>,
  ).replace(/<!--.*?-->/g, '')
}

/** Роутер нужен любому рендеру строки: заголовок ведёт в просмотрщик. */
function renderRow(props: Partial<Parameters<typeof GuidelineRow>[0]> = {}) {
  return render(
    <MemoryRouter>
      <ul>
        <GuidelineRow guideline={GUIDELINE} {...props} />
      </ul>
    </MemoryRouter>,
  )
}

describe('GuidelineRow', () => {
  it('показывает название, файл, размер, дату и версию', () => {
    const html = renderToStringOf(GUIDELINE)

    expect(html).toContain('Гипертензия')
    expect(html).toContain('КР62_3.pdf')
    expect(html).toContain('3,1 МБ')
    expect(html).toContain('версия 1')
    expect(html).toMatch(/\d{2}\.\d{2}\.\d{4}/)
  })

  it('ведёт в просмотрщик этого клинрека', () => {
    expect(renderToStringOf(GUIDELINE)).toContain(
      'href="/library/5fc51635-7cdf-4efe-99dd-fa7028434376/view"',
    )
  })

  it('показывает статус из ответа сервера, не выдавая загруженный за готовый', () => {
    const html = renderToStringOf(GUIDELINE)

    expect(html).toContain('Загружен')
    expect(html).not.toContain('Готов к проверке')
  })

  it('показывает причину падения при статусе failed', () => {
    const html = renderToStringOf({ ...GUIDELINE, status: 'failed', error: 'pdf parsing failed' })

    expect(html).toContain('Ошибка обработки')
    expect(html).toContain('pdf parsing failed')
  })

  it('показывает все коды МКБ клинрека', () => {
    const html = renderToStringOf(GUIDELINE)

    expect(html).toContain('>I10<')
    expect(html).toContain('>I15<')
  })

  it('сообщает, что коды не указаны, и не прячет строку', () => {
    const html = renderToStringOf({ ...GUIDELINE, icd_codes: [] })

    expect(html).toContain('коды МКБ не указаны')
    expect(html).toContain('Гипертензия')
  })

  it('нумерует строку в желобе', () => {
    expect(renderToStringOf(GUIDELINE, { index: 3 })).toContain('>03<')
  })

  it('показывает полосу обработки и её процент', () => {
    const html = renderToStringOf({
      ...GUIDELINE,
      status: 'processing',
      chunks_total: 120,
      chunks_indexed: 34,
    })

    expect(html).toContain('Обработано 34 из 120 фрагментов')
    expect(html).toContain('role="progressbar"')
    expect(html).toContain('width:28%')
  })
})

/** Строка с управлением фазами удаления: логика живёт в экране, здесь только рендер. */
function DeleteHarness({ onConfirm }: { onConfirm?: (id: string) => void }) {
  const [phase, setPhase] = useState<DeletePhase>('idle')

  return (
    <MemoryRouter>
      <ul>
        <GuidelineRow
          guideline={GUIDELINE}
          deletePhase={phase}
          onRequestDelete={() => setPhase('confirming')}
          onConfirmDelete={(id) => {
            setPhase('deleting')
            onConfirm?.(id)
          }}
          onCancelDelete={() => setPhase('idle')}
        />
      </ul>
    </MemoryRouter>
  )
}

describe('удаление клинрека', () => {
  it('без обработчиков не предлагает удаление', () => {
    expect(renderToStringOf(GUIDELINE)).not.toContain('Удалить')
  })

  it('просит подтверждение диалогом вместо немедленного удаления', async () => {
    const user = userEvent.setup()
    let confirmed: string | null = null
    render(<DeleteHarness onConfirm={(id) => (confirmed = id)} />)

    await user.click(screen.getByRole('button', { name: 'Удалить' }))

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('Удалить клинрек?')).toBeTruthy()
    expect(confirmed).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Подтвердить' }))
    expect(confirmed).toBe('5fc51635-7cdf-4efe-99dd-fa7028434376')
  })

  it('отменяется по Esc, не отправляя запрос, и возвращает фокус', async () => {
    const user = userEvent.setup()
    let confirmed: string | null = null
    render(<DeleteHarness onConfirm={(id) => (confirmed = id)} />)

    const trigger = screen.getByRole('button', { name: 'Удалить' })
    await user.click(trigger)
    await user.keyboard('{Escape}')

    expect(confirmed).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(document.activeElement).toBe(trigger))
  })

  it('показывает ход удаления и блокирует повтор', () => {
    renderRow({
      onRequestDelete: () => {},
      onConfirmDelete: () => {},
      onCancelDelete: () => {},
      deletePhase: 'deleting',
    })

    expect(screen.getByRole('dialog')).toBeTruthy()
    const confirm = screen.getByRole('button', { name: 'Удаляем…' })
    expect(confirm.hasAttribute('disabled')).toBe(true)
  })

  it('показывает причину отказа и способ её закрыть', () => {
    const html = renderToStringOf(GUIDELINE, {
      onRequestDelete: () => {},
      onConfirmDelete: () => {},
      onCancelDelete: () => {},
      deletePhase: 'error',
      deleteError: 'По клинреку идёт индексация.',
    })

    expect(html).toContain('По клинреку идёт индексация.')
    expect(html).toContain('Закрыть')
  })
})
