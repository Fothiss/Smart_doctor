import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { askChat } from '../api/chat'
import { describeError } from '../api/client'
import { type Guideline, listGuidelines } from '../api/guidelines'
import { ChatComposer } from '../components/chat/ChatComposer'
import { ChatEmptyState } from '../components/chat/ChatEmptyState'
import { DocumentsBar } from '../components/chat/DocumentsBar'
import { MessageThread } from '../components/chat/MessageThread'
import type { MultiComboboxItem } from '../components/ui/MultiCombobox'
import { matchesGuidelineQuery } from '../lib/guidelineSearch'
import {
  MAX_DOCS,
  askRequest,
  canAsk,
  readSelectedDocs,
  writeSelectedDocs,
} from '../store/chat'
import { useChatSession } from '../store/chatSession'

type GuidelinesState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; items: Guideline[] }

type AskState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string; question: string }

/** Подпись документа в выборе: название, коды МКБ и имя файла. */
function describeGuideline(guideline: Guideline): string {
  const codes = (guideline.icd_codes ?? []).join(', ')
  return codes === ''
    ? `${guideline.title} · ${guideline.filename}`
    : `${guideline.title} · ${codes} · ${guideline.filename}`
}

const SUGGESTIONS = [
  'До какого давления снижать пациенту 60 лет с диабетом?',
  'Какие препараты первой линии при гипертензии 2 степени?',
  'Как часто контролировать давление после начала терапии?',
]

/**
 * Экран чата по выбранным клинрекам.
 *
 * Лента как в обычном чате: вопрос справа, ответ слева с источниками. Выбранные документы
 * живут в адресе, поэтому ссылкой на подборку можно поделиться, а обновление страницы не
 * теряет выбор. Сервер ленту не хранит: каждая реплика самодостаточна.
 */
export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [guidelines, setGuidelines] = useState<GuidelinesState>({ kind: 'loading' })
  // Лента и черновик живут в сессии приложения: переход в библиотеку их не теряет,
  // а перезагрузка страницы начинает разговор заново
  const { entries, draft, append, setDraft, reset } = useChatSession()
  const [ask, setAsk] = useState<AskState>({ kind: 'idle' })
  const bottomRef = useRef<HTMLDivElement>(null)

  const selected = readSelectedDocs(searchParams)

  useEffect(() => {
    const controller = new AbortController()

    void (async () => {
      try {
        const items = await listGuidelines({ status: 'ready' }, { signal: controller.signal })
        if (!controller.signal.aborted) {
          setGuidelines({ kind: 'ready', items })
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setGuidelines({ kind: 'error', message: describeError(caught) })
        }
      }
    })()

    return () => controller.abort()
  }, [])

  // Новая реплика должна быть видна: лента сама доезжает до конца
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [entries, ask.kind])

  const readyItems = guidelines.kind === 'ready' ? guidelines.items : []
  const byId = new Map(readyItems.map((item) => [item.guideline_id, item]))
  const comboboxItems: MultiComboboxItem[] = readyItems.map((guideline) => ({
    value: guideline.guideline_id,
    label: describeGuideline(guideline),
  }))
  const pending = ask.kind === 'loading'
  const canSubmit = canAsk(draft, selected) && !pending

  const documentsState =
    guidelines.kind === 'ready'
      ? readyItems.length === 0
        ? 'empty'
        : 'ready'
      : guidelines.kind

  function handleSelection(next: string[]): void {
    setSearchParams(writeSelectedDocs(searchParams, next), { replace: true })
  }

  function resetChat(): void {
    reset()
    setAsk({ kind: 'idle' })
  }

  async function send(text: string): Promise<void> {
    const ids = selected
    if (!canAsk(text, ids)) {
      return
    }
    setAsk({ kind: 'loading' })
    try {
      const answer = await askChat(askRequest(ids, text, entries))
      append({ question: text.trim(), answer })
      setDraft('')
      setAsk({ kind: 'idle' })
    } catch (caught) {
      setAsk({ kind: 'error', message: describeError(caught), question: text })
    }
  }

  function hint(): string | undefined {
    if (selected.length === 0) {
      return 'Сначала выберите хотя бы один документ'
    }
    if (entries.length > 0) {
      return `Поиск идёт по ${selected.length} док. · Enter — отправить, Shift+Enter — новая строка`
    }
    return undefined
  }

  return (
    <section className="flex min-h-0 w-full flex-1 flex-col" aria-busy={pending}>
      <DocumentsBar
        state={documentsState}
        errorMessage={guidelines.kind === 'error' ? guidelines.message : undefined}
        items={comboboxItems}
        selected={selected}
        onChange={handleSelection}
        limit={MAX_DOCS}
        matchQuery={(item, needle) => {
          const guideline = byId.get(item.value)
          return guideline === undefined ? false : matchesGuidelineQuery(guideline, needle)
        }}
        onReset={entries.length === 0 ? undefined : resetChat}
      />

      <div className="min-h-0 flex-1 overflow-y-auto py-4">
        <MessageThread
          entries={entries}
          pending={pending}
          error={ask.kind === 'error' ? { message: ask.message } : null}
          onRetry={() => {
            if (ask.kind === 'error') {
              void send(ask.question)
            }
          }}
          emptyState={
            <ChatEmptyState suggestions={SUGGESTIONS} onPick={(text) => setDraft(text)} />
          }
        />
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border pt-3">
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSubmit={() => void send(draft)}
          disabled={!canSubmit}
          pending={pending}
          hint={hint()}
        />
      </div>
    </section>
  )
}
