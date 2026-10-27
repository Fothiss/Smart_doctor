// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import type { ChatCitation } from '../../api/chat'
import { AnswerText, markCitations } from './AnswerText'

const GUIDELINE_ID = '7434ecc7-58ec-4925-9b93-cb4d507646ca'
const CHUNK_A = '4f1d6e2a-1111-4222-8333-944455556666'
const CHUNK_B = '7a2c9e11-3333-4444-9555-666677778888'

function citation(n: number, chunkId: string): ChatCitation {
  return {
    n,
    chunk_id: chunkId,
    guideline_id: GUIDELINE_ID,
    guideline_version: 1,
    guideline_title: 'Гипертензия',
    section: '3.2. Целевые уровни',
    page: 9,
    quote: 'Целевой уровень АД — ниже 140/90 мм рт. ст.',
  }
}

const CITATIONS = [citation(1, CHUNK_A), citation(2, CHUNK_B)]

afterEach(cleanup)

function renderAnswer(answer: string, citations: readonly ChatCitation[] = CITATIONS) {
  return render(
    <MemoryRouter>
      <AnswerText answer={answer} citations={citations} />
    </MemoryRouter>,
  )
}

describe('AnswerText', () => {
  it('маркеры превращаются в markdown-ссылки на фрагмент', () => {
    const labels = new Map([
      [1, 1],
      [2, 2],
    ])

    expect(markCitations('до 140/90 [1]', labels)).toBe('до 140/90 [1](#cite-1)')
  })

  it('разводит перечисление, склеенное моделью в одну строку', () => {
    const { container } = renderAnswer(
      'Общие принципы: - Пациентам с АГ 2-й степени рекомендуется комбинация 8. - Базовые схемы включают иРААС [1, 5]. - При ХБП можно все группы АГП.',
    )

    expect(container.querySelectorAll('ul > li')).toHaveLength(3)
  })

  it('выводит маркированный список пунктами, а не строкой', () => {
    const { container } = renderAnswer('- первый пункт [1]\n- второй пункт')

    expect(container.querySelectorAll('li')).toHaveLength(2)
  })

  it('выводит нумерованный список', () => {
    const { container } = renderAnswer('1. первый\n2. второй\n3. третий')

    expect(container.querySelectorAll('ol > li')).toHaveLength(3)
  })

  it('сохраняет выделение жирным', () => {
    const { container } = renderAnswer('**Амлодипин** 5 мг')

    expect(container.querySelector('strong')?.textContent).toBe('Амлодипин')
  })

  it('маркер внутри списка ведёт на просмотрщик фрагмента', () => {
    renderAnswer('- контроль [1] через две недели')

    const link = screen.getByRole('link', { name: 'Источник 1' })

    expect(link.getAttribute('href')).toBe(`/library/${GUIDELINE_ID}/view?chunk=${CHUNK_A}`)
  })

  it('нумерует ссылки подряд, даже если модель сослалась на фрагменты 4 и 5', () => {
    renderAnswer('схемы [4] и [5]', [citation(4, CHUNK_A), citation(5, CHUNK_B)])

    const first = screen.getByRole('link', { name: 'Источник 1' })
    const second = screen.getByRole('link', { name: 'Источник 2' })

    expect(first.textContent).toBe('1')
    expect(second.textContent).toBe('2')
    expect(first.getAttribute('href')).toBe(`/library/${GUIDELINE_ID}/view?chunk=${CHUNK_A}`)
    expect(second.getAttribute('href')).toBe(`/library/${GUIDELINE_ID}/view?chunk=${CHUNK_B}`)
  })

  it('разбирает групповой маркер на отдельные ссылки', () => {
    renderAnswer('схемы [1, 2]', CITATIONS)

    expect(screen.getByRole('link', { name: 'Источник 1' }).textContent).toBe('1')
    expect(screen.getByRole('link', { name: 'Источник 2' }).textContent).toBe('2')
  })

  it('маркер без подтверждённой ссылки остаётся текстом', () => {
    renderAnswer('ответ [7]')

    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText(/ответ/, { exact: false })).toBeTruthy()
  })

  it('внешнюю ссылку модели показывает текстом, а не переходом', () => {
    renderAnswer('см. [сайт](https://example.com)')

    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByText('сайт')).toBeTruthy()
  })

  it('внутреннюю ссылку оставляет кликабельной', () => {
    renderAnswer('откройте [библиотеку](/library)')

    const link = screen.getByRole('link', { name: 'библиотеку' })

    expect(link.getAttribute('href')).toBe('/library')
  })

  it('таблицу выводит таблицей', () => {
    const { container } = renderAnswer('| Препарат | Доза |\n| --- | --- |\n| Амлодипин | 5 мг |')

    expect(container.querySelectorAll('table th')).toHaveLength(2)
    expect(container.querySelectorAll('table td')).toHaveLength(2)
  })
})
