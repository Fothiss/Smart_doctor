import { describe, expect, it } from 'vitest'

import {
  type ChatEntry,
  HISTORY_WINDOW,
  askRequest,
  buildHistory,
  canAsk,
  citationHref,
  citationIndex,
  isAnswered,
  readSelectedDocs,
  writeSelectedDocs,
} from './chat'
import type { ChatAnswer } from '../api/chat'

const GUIDELINE_ID = '7434ecc7-58ec-4925-9b93-cb4d507646ca'
const CHUNK_ID = '4f1d6e2a-1111-4222-8333-944455556666'

function answer(overrides: Partial<ChatAnswer> = {}): ChatAnswer {
  return {
    status: 'answered',
    answer: 'Снижать до 140/90 [1].',
    citations: [
      {
        n: 1,
        chunk_id: CHUNK_ID,
        guideline_id: GUIDELINE_ID,
        guideline_version: 1,
        guideline_title: 'Гипертензия',
        section: '3.2. Целевые уровни',
        page: 9,
        quote: 'ниже 140/90 мм рт. ст.',
      },
    ],
    search: { expression: 'целевой уровень АД', rewritten: true, constraints_lost: 0 },
    searched_guidelines: [{ guideline_id: GUIDELINE_ID, title: 'Гипертензия', version: 1 }],
    ...overrides,
  }
}

function entry(question: string): ChatEntry {
  return { question, answer: answer() }
}

describe('выбранные документы в адресе', () => {
  it('читает список и отбрасывает пустые значения', () => {
    expect(readSelectedDocs(new URLSearchParams(`docs=${GUIDELINE_ID},,`))).toEqual([GUIDELINE_ID])
  })

  it('пустой параметр означает пустой выбор', () => {
    expect(readSelectedDocs(new URLSearchParams(''))).toEqual([])
  })

  it('снимает повторы: дважды выбранный документ не удваивается', () => {
    expect(readSelectedDocs(new URLSearchParams(`docs=${GUIDELINE_ID},${GUIDELINE_ID}`))).toEqual([
      GUIDELINE_ID,
    ])
  })

  it('записывает выбор и убирает параметр при пустом списке', () => {
    const written = writeSelectedDocs(new URLSearchParams('status=ready'), [GUIDELINE_ID])

    expect(written.get('docs')).toBe(GUIDELINE_ID)
    expect(written.get('status')).toBe('ready')
    expect(writeSelectedDocs(written, []).get('docs')).toBeNull()
  })
})

describe('готовность вопроса', () => {
  it('без документов спрашивать нельзя', () => {
    expect(canAsk('вопрос', [])).toBe(false)
  })

  it('с документом и текстом можно', () => {
    expect(canAsk('вопрос', [GUIDELINE_ID])).toBe(true)
  })

  it('пробелы вместо вопроса не считаются вопросом', () => {
    expect(canAsk('   ', [GUIDELINE_ID])).toBe(false)
  })
})

describe('окно истории', () => {
  it('оставляет только последние сообщения окна', () => {
    const entries = [entry('первый'), entry('второй'), entry('третий')]

    const history = buildHistory(entries)

    expect(history).toHaveLength(HISTORY_WINDOW)
    expect(history[history.length - 1]?.text).toBe('Снижать до 140/90 [1].')
    expect(history.some((message) => message.text === 'первый')).toBe(false)
  })

  it('нулевое окно отключает историю', () => {
    expect(buildHistory([entry('вопрос')], 0)).toEqual([])
  })

  it('в запрос уходят выбранные документы и текст вопроса', () => {
    const request = askRequest([GUIDELINE_ID], '  вопрос  ', [])

    expect(request.guideline_ids).toEqual([GUIDELINE_ID])
    expect(request.question).toBe('вопрос')
    expect(request.history).toEqual([])
  })
})

describe('ссылка на фрагмент', () => {
  it('ведёт в просмотрщик с идентификатором фрагмента', () => {
    expect(citationHref(GUIDELINE_ID, CHUNK_ID)).toBe(
      `/library/${GUIDELINE_ID}/view?chunk=${CHUNK_ID}`,
    )
  })
})

describe('номера источников', () => {
  it('собирает карту «номер → адрес фрагмента»', () => {
    const index = citationIndex(answer())

    expect(index.get(1)).toEqual({ guideline_id: GUIDELINE_ID, chunk_id: CHUNK_ID })
    expect(index.get(2)).toBeUndefined()
  })

  it('отказ не считается ответом', () => {
    expect(isAnswered(answer({ status: 'not_found', answer: null, citations: [] }))).toBe(false)
    expect(isAnswered(answer())).toBe(true)
  })
})
