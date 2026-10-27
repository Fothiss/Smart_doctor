import { Check, ChevronDown, X } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'

import { cn } from './cn'
import { controlClassName } from './Field'

export type MultiComboboxItem = {
  value: string
  label: string
}

export type MultiComboboxProps = {
  items: readonly MultiComboboxItem[]
  values: readonly string[]
  onChange: (values: string[]) => void
  /** Подпись для вспомогательных технологий. */
  label: string
  /** Сколько значений можно выбрать одновременно. */
  limit: number
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  limitText?: string
  /** Своя проверка совпадения: поиск по нескольким полям, а не только по подписи. */
  matchQuery?: (item: MultiComboboxItem, needle: string) => boolean
  id?: string
  className?: string
}

/**
 * Выбор нескольких значений из длинного списка с поиском.
 *
 * Отличие от `Combobox` в том, что список не закрывается после выбора: врач набирает
 * несколько документов подряд, а выбранное видно чипами у поля — иначе при четырёх
 * документах пришлось бы помнить, что уже отмечено.
 */
export function MultiCombobox({
  items,
  values,
  onChange,
  label,
  limit,
  placeholder = 'Выберите документы',
  searchPlaceholder = 'Поиск по названию, файлу или коду МКБ',
  emptyText = 'Ничего не найдено',
  limitText = 'Больше документов выбрать нельзя',
  matchQuery,
  id,
  className,
}: MultiComboboxProps) {
  const generatedId = useId()
  const triggerId = id ?? `multicombobox-${generatedId}`
  const listId = `${triggerId}-listbox`

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('ru')
    if (needle === '') {
      return items
    }
    return items.filter((item) =>
      matchQuery !== undefined
        ? matchQuery(item, needle)
        : item.label.toLocaleLowerCase('ru').includes(needle),
    )
  }, [items, query, matchQuery])

  const selected = useMemo(
    () => items.filter((item) => values.includes(item.value)),
    [items, values],
  )
  const atLimit = values.length >= limit

  useEffect(() => {
    if (!open) {
      return
    }
    function handlePointerDown(event: PointerEvent): void {
      if (rootRef.current !== null && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [open])

  function toggle(value: string): void {
    if (values.includes(value)) {
      onChange(values.filter((item) => item !== value))
      return
    }
    if (atLimit) {
      return
    }
    onChange([...values, value])
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      setQuery('')
    }
  }

  return (
    <div ref={rootRef} className={cn('relative flex flex-col gap-1', className)}>
      <button
        id={triggerId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={label}
        onClick={() => setOpen((current) => !current)}
        className={cn(controlClassName, 'flex h-9 w-full items-center justify-between gap-2 text-left')}
      >
        <span className={values.length === 0 ? 'text-text-faint' : undefined}>
          {values.length === 0 ? placeholder : `Выбрано документов: ${values.length}`}
        </span>
        <ChevronDown aria-hidden="true" size={16} className="shrink-0 text-text-muted" />
      </button>

      {selected.length === 0 ? null : (
        <ul className="flex flex-wrap gap-1" aria-label="Выбранные документы">
          {selected.map((item) => (
            <li
              key={item.value}
              className="flex items-center gap-1 rounded-chip bg-accent-soft px-2 py-0.5 text-caption text-accent"
            >
              <span>{item.label}</span>
              <button
                type="button"
                aria-label={`Убрать ${item.label}`}
                onClick={() => onChange(values.filter((value) => value !== item.value))}
                className="cursor-pointer text-accent"
              >
                <X aria-hidden="true" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {open ? (
        <div className="absolute top-full z-30 mt-1 w-full rounded-card border border-border bg-surface p-2 shadow-panel">
          <input
            // Список только что открыт действием пользователя: искать нужно сразу
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            type="text"
            value={query}
            aria-label={searchPlaceholder}
            placeholder={searchPlaceholder}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
            className={controlClassName}
          />
          {filtered.length === 0 ? (
            <p className="mt-2 px-2 py-1.5 text-caption text-text-muted">{emptyText}</p>
          ) : (
            <div
              id={listId}
              role="listbox"
              aria-label={label}
              aria-multiselectable="true"
              className="mt-2 max-h-64 overflow-auto"
            >
              {filtered.map((item) => {
                const isSelected = values.includes(item.value)
                return (
                  <button
                    key={item.value}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={!isSelected && atLimit}
                    className={cn(
                      'flex w-full cursor-pointer items-center justify-between gap-2 rounded-chip px-2 py-1.5 text-left text-body',
                      isSelected ? 'bg-accent-soft text-ink' : 'text-text',
                      !isSelected && atLimit ? 'cursor-default opacity-55' : undefined,
                    )}
                    onClick={() => toggle(item.value)}
                  >
                    <span>{item.label}</span>
                    {isSelected ? <Check aria-hidden="true" size={14} /> : null}
                  </button>
                )
              })}
            </div>
          )}
          {atLimit ? (
            <p role="status" className="mt-2 px-2 text-caption text-text-muted">
              {limitText}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
