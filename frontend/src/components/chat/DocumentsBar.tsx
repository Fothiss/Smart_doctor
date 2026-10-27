import { Library, Paperclip, SquarePen } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '../ui/Button'
import { MultiCombobox, type MultiComboboxItem } from '../ui/MultiCombobox'

export type DocumentsBarProps = {
  state: 'loading' | 'error' | 'empty' | 'ready'
  errorMessage?: string
  items: readonly MultiComboboxItem[]
  selected: readonly string[]
  onChange: (values: string[]) => void
  limit: number
  matchQuery?: (item: MultiComboboxItem, needle: string) => boolean
  /** Очистка ленты: кнопка появляется, когда в чате уже есть реплики. */
  onReset?: () => void
}

/**
 * Верхняя строка чата с выбором документов.
 *
 * Выбор стоит над лентой, как выбор модели в знакомых чатах: видно, по каким документам
 * пойдёт ответ, и можно поменять набор, не теряя переписку.
 */
export function DocumentsBar({
  state,
  errorMessage,
  items,
  selected,
  onChange,
  limit,
  matchQuery,
  onReset,
}: DocumentsBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border pb-3">
      <span className="flex items-center gap-1 text-caption text-text-muted">
        <Paperclip aria-hidden="true" size={14} />
        Документы
      </span>

      {state === 'loading' ? <span className="text-caption text-text-faint">Загружаем…</span> : null}

      {state === 'error' ? (
        <span role="alert" className="text-caption text-danger">
          Не удалось получить список: {errorMessage}
        </span>
      ) : null}

      {state === 'empty' ? (
        <span className="flex items-center gap-2 text-caption text-text-muted">
          Нет готовых клинреков
          <Link to="/library" className="inline-flex items-center gap-1 text-accent">
            <Library aria-hidden="true" size={14} />в библиотеку
          </Link>
        </span>
      ) : null}

      {state === 'ready' ? (
        <div className="w-full min-w-0 sm:w-[26rem]">
          <MultiCombobox
            items={items}
            values={selected}
            onChange={onChange}
            label="Документы для поиска"
            limit={limit}
            matchQuery={matchQuery}
            placeholder="Выберите документы"
          />
        </div>
      ) : null}

      <span className="text-caption text-text-faint">не больше {limit}</span>

      {onReset === undefined ? null : (
        <Button variant="ghost" size="sm" className="ml-auto" onClick={onReset}>
          <SquarePen aria-hidden="true" size={14} />
          Новый чат
        </Button>
      )}
    </div>
  )
}
