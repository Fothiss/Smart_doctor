import Markdown, { type Components } from 'react-markdown'
import { Link } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import type { ChatCitation } from '../../api/chat'
import { citationHref } from '../../store/chat'
import { normalizeLists } from './markdown'

const CITE_PREFIX = '#cite-'
const GROUP = /\[(\d+(?:\s*,\s*\d+)*)\]/g

/**
 * Разметить ссылки ответа для markdown.
 *
 * `[4]` → `[1](#cite-4)`, `[3, 5]` → `[1](#cite-3), [2](#cite-5)`: в тексте ссылки
 * нумеруются подряд, а адресом остаётся номер фрагмента в контексте модели. Модель
 * ссылается на фрагменты всего контекста, и без перенумерации в ответе появляются
 * дыры вида «[4] и [5]».
 */
export function markCitations(answer: string, labels: Map<number, number>): string {
  return answer.replace(GROUP, (_match, group: string) => {
    const numbers = group
      .split(',')
      .map((part) => Number(part.trim()))
      .filter((number) => Number.isInteger(number))
    return numbers
      .map((number) => {
        const label = labels.get(number)
        return label === undefined ? `[${number}]` : `[${label}](#cite-${number})`
      })
      .join(', ')
  })
}

export type AnswerTextProps = {
  answer: string
  /** Подтверждённые ссылки в порядке появления: этот порядок задаёт нумерацию в тексте. */
  citations: readonly ChatCitation[]
}

/**
 * Ответ модели как markdown.
 *
 * GigaChat отвечает списками, выделениями и таблицами — в plain text они схлопываются в
 * портянку. Ссылки ограничены: переход разрешён только на фрагмент клинрека или на экран
 * приложения, внешние адреса остаются текстом — ответ не должен уводить врача из источников.
 */
export function AnswerText({ answer, citations }: AnswerTextProps) {
  const labels = new Map(citations.map((citation, index) => [citation.n, index + 1]))
  const byNumber = new Map(citations.map((citation) => [citation.n, citation]))

  const components: Components = {
    p: ({ children }) => <p className="text-body leading-relaxed text-text">{children}</p>,
    ul: ({ children }) => (
      <ul className="flex list-disc flex-col gap-1 pl-5 text-body text-text">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="flex list-decimal flex-col gap-1 pl-5 text-body text-text">{children}</ol>
    ),
    li: ({ children }) => <li className="pl-0.5">{children}</li>,
    strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
    em: ({ children }) => <em className="italic">{children}</em>,
    h1: ({ children }) => <p className="text-h3 font-semibold text-ink">{children}</p>,
    h2: ({ children }) => <p className="text-h3 font-semibold text-ink">{children}</p>,
    h3: ({ children }) => <p className="text-lead font-semibold text-ink">{children}</p>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-border-strong pl-3 text-text-muted">
        {children}
      </blockquote>
    ),
    code: ({ children }) => (
      <code className="rounded-chip bg-surface-sunken px-1 py-0.5 font-mono text-caption">
        {children}
      </code>
    ),
    pre: ({ children }) => (
      <pre className="overflow-x-auto rounded-chip bg-surface-sunken p-2 font-mono text-caption">
        {children}
      </pre>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-caption">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border border-border bg-surface-sunken px-2 py-1 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }) => <td className="border border-border px-2 py-1 align-top">{children}</td>,
    a: ({ href, children }) => (
      <AnswerLink href={href} citations={byNumber}>
        {children}
      </AnswerLink>
    ),
  }

  return (
    <div className="flex flex-col gap-2">
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {markCitations(normalizeLists(answer), labels)}
      </Markdown>
    </div>
  )
}

/** Ссылка внутри ответа: фрагмент клинрека или экран приложения, но не внешний адрес. */
function AnswerLink({
  href,
  children,
  citations,
}: {
  href?: string
  children?: React.ReactNode
  citations: Map<number, ChatCitation>
}) {
  if (href === undefined) {
    return <span>{children}</span>
  }

  if (href.startsWith(CITE_PREFIX)) {
    const n = Number(href.slice(CITE_PREFIX.length))
    const citation = citations.get(n)
    if (citation === undefined) {
      return <span>{children}</span>
    }
    return (
      <Link
        to={citationHref(citation.guideline_id, citation.chunk_id)}
        aria-label={`Источник ${String(children)}`}
        className="mx-0.5 rounded-chip bg-accent-soft px-1 text-caption font-medium text-accent no-underline hover:bg-accent hover:text-accent-text"
      >
        {children}
      </Link>
    )
  }

  if (href.startsWith('/')) {
    return (
      <Link to={href} className="text-accent underline-offset-2 hover:underline">
        {children}
      </Link>
    )
  }

  // Внешние адреса модель придумывает сама: показываем текст, а не переход
  return <span>{children}</span>
}
