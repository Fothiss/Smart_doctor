import { MessageSquareQuote, RotateCcw, Stethoscope, User } from 'lucide-react'
import { type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '../ui/Button'
import { Mono } from '../ui/Typography'
import {
  type ChatEntry,
  citationHref,
  citationsOf,
  isAnswered,
  searchedTitles,
} from '../../store/chat'
import { AnswerText } from './AnswerText'

export type MessageThreadProps = {
  entries: readonly ChatEntry[]
  pending: boolean
  error: { message: string } | null
  onRetry: () => void
  /** Что показать, пока лента пуста. */
  emptyState: ReactNode
}

/**
 * Лента чата: вопрос врача справа, ответ ассистента слева с источниками.
 *
 * Ответ без подтверждённых ссылок показывается как отказ, а не как ответ: экран не должен
 * делать вид, что система знает больше, чем подкрепила цитатой.
 */
export function MessageThread({ entries, pending, error, onRetry, emptyState }: MessageThreadProps) {
  if (entries.length === 0 && !pending && error === null) {
    return <>{emptyState}</>
  }

  return (
    <ol className="flex flex-col gap-5" aria-label="Диалог">
      {entries.map((entry, index) => (
        <li key={`${index}-${entry.question}`} className="flex flex-col gap-3">
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-panel rounded-br-chip bg-accent-soft px-4 py-2 text-body text-ink">
              <span className="sr-only">Вопрос: </span>
              {entry.question}
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-pill bg-surface-sunken text-accent">
              <Stethoscope aria-hidden="true" size={15} />
              <span className="sr-only">Ответ ассистента</span>
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-3 rounded-panel rounded-tl-chip border border-border bg-surface px-4 py-3 shadow-card">
              {isAnswered(entry.answer) ? (
                <AnswerBody entry={entry} />
              ) : (
                <div className="flex flex-col gap-1">
                  <p className="text-body font-medium text-ink">В выбранных документах нет ответа</p>
                  <p className="text-caption text-text-muted">
                    Переформулируйте вопрос или добавьте документ — система не отвечает по памяти
                    модели.
                  </p>
                </div>
              )}
              <SearchFootnote entry={entry} />
            </div>
          </div>
        </li>
      ))}

      {pending ? (
        <li className="flex items-start gap-2">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-pill bg-surface-sunken text-accent">
            <Stethoscope aria-hidden="true" size={15} />
          </span>
          <div className="flex items-center gap-2 rounded-panel rounded-tl-chip border border-border bg-surface px-4 py-3 shadow-card">
            <span className="flex gap-1" aria-hidden="true">
              <Dot delay="0ms" />
              <Dot delay="150ms" />
              <Dot delay="300ms" />
            </span>
            <span className="text-caption text-text-muted">Ищем по выбранным документам…</span>
          </div>
        </li>
      ) : null}

      {error === null ? null : (
        <li className="flex items-start gap-2">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-pill bg-danger-bg text-danger">
            <User aria-hidden="true" size={15} />
          </span>
          <div
            role="alert"
            className="flex flex-col gap-2 rounded-panel rounded-tl-chip border border-danger bg-danger-bg px-4 py-3"
          >
            <p className="text-body font-medium text-danger">Не удалось получить ответ</p>
            <p className="text-caption text-danger">{error.message}</p>
            <div>
              <Button variant="secondary" size="sm" onClick={onRetry}>
                <RotateCcw aria-hidden="true" size={14} />
                Повторить
              </Button>
            </div>
          </div>
        </li>
      )}
    </ol>
  )
}

/** Ответ как markdown: разметка модели плюс список источников под текстом. */
function AnswerBody({ entry }: { entry: ChatEntry }) {
  const citations = citationsOf(entry.answer)
  return (
    <div className="flex flex-col gap-3">
      <AnswerText answer={entry.answer.answer ?? ''} citations={citations} />
      <ul className="flex flex-col gap-1.5" aria-label="Источники ответа">
        {citations.map((citation, index) => (
          <li key={citation.chunk_id}>
            <Link
              to={citationHref(citation.guideline_id, citation.chunk_id)}
              className="flex gap-2 rounded-chip border border-border bg-surface-sunken px-2 py-1.5 text-caption text-text no-underline hover:border-accent hover:text-accent"
            >
              <MessageSquareQuote aria-hidden="true" size={14} className="mt-0.5 shrink-0" />
              <span className="flex flex-col gap-0.5">
                <span className="font-medium">
                  [{index + 1}] {citation.guideline_title}
                  {citation.section === null ? '' : `, ${citation.section}`}, стр. {citation.page}
                </span>
                <span className="text-text-muted">{citation.quote}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Строка прозрачности: по каким документам и с какой формулировкой шёл поиск. */
function SearchFootnote({ entry }: { entry: ChatEntry }) {
  return (
    <p className="text-caption text-text-faint">
      Поиск: {searchedTitles(entry.answer)} · запрос <Mono>{entry.answer.search.expression}</Mono>
      {entry.answer.search.constraints_lost > 0
        ? ` · при переформулировке потеряно условий: ${entry.answer.search.constraints_lost}`
        : ''}
    </p>
  )
}

/** Пульсирующая точка ожидания: ответ идёт, интерфейс жив. */
function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="size-1.5 animate-pulse rounded-pill bg-text-faint"
      style={{ animationDelay: delay }}
    />
  )
}
