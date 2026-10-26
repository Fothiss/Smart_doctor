import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'

import { cn } from './cn'
import { controlClassName } from './Field'

export type ComboboxItem = {
  value: string
  label: string
}

export type ComboboxProps = {
  items: readonly ComboboxItem[]
  value: string | null
  onChange: (value: string) => void
  /** Подпись выбора для вспомогательных технологий. */
  label: string
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  id?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
  className?: string
}

/**
 * Выбор из длинного списка с поиском.
 *
 * Поиск фильтрует подписи по подстроке, стрелки двигают активный вариант, Enter выбирает,
 * Esc закрывает список без изменения значения. Список закрывается и по клику вне компонента.
 */
export function Combobox({
  items,
  value,
  onChange,
  label,
  placeholder = 'Выберите значение',
  searchPlaceholder = 'Поиск',
  emptyText = 'Ничего не найдено',
  id,
  'aria-describedby': describedBy,
  'aria-invalid': invalid,
  className,
}: ComboboxProps) {
  const generatedId = useId()
  const triggerId = id ?? `combobox-${generatedId}`
  const listId = `${triggerId}-listbox`

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('ru')
    if (needle === '') {
      return items
    }
    return items.filter((item) => item.label.toLocaleLowerCase('ru').includes(needle))
  }, [items, query])

  const selected = items.find((item) => item.value === value) ?? null
  // Список мог сузиться после ввода: активный вариант не должен выпадать из него
  const active = filtered.length === 0 ? -1 : Math.min(activeIndex, filtered.length - 1)

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

  function select(next: string): void {
    onChange(next)
    setOpen(false)
    setQuery('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex(active + 1 >= filtered.length ? 0 : active + 1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex(active - 1 < 0 ? Math.max(filtered.length - 1, 0) : active - 1)
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const item = filtered[active]
      if (item !== undefined) {
        select(item.value)
      }
      return
    }
    if (event.key === 'Escape') {
      // Закрытие без выбора: значение не меняется
      event.preventDefault()
      setOpen(false)
      setQuery('')
    }
  }

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button
        id={triggerId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-describedby={describedBy}
        data-invalid={invalid === true ? 'true' : undefined}
        onClick={() => {
          setOpen((current) => !current)
          setActiveIndex(0)
        }}
        className={cn(
          controlClassName,
          'flex h-9 w-full items-center justify-between gap-2 text-left',
        )}
      >
        <span className={selected === null ? 'text-text-faint' : undefined}>
          {selected?.label ?? placeholder}
        </span>
        <ChevronDown aria-hidden="true" size={16} className="shrink-0 text-text-muted" />
      </button>

      {open ? (
        <div className="absolute z-30 mt-1 w-full rounded-card border border-border bg-surface p-2 shadow-panel">
          <input
            // Список только что открыт действием пользователя: искать нужно сразу, без лишнего Tab
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            type="text"
            value={query}
            aria-label={searchPlaceholder}
            aria-controls={listId}
            aria-activedescendant={active >= 0 ? `${triggerId}-option-${active}` : undefined}
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
              className="mt-2 max-h-64 overflow-auto"
            >
              {filtered.map((item, index) => (
                <div
                  key={item.value}
                  id={`${triggerId}-option-${index}`}
                  role="option"
                  aria-selected={item.value === value}
                  // Фокус живёт в поле поиска: вариант выбирается через aria-activedescendant
                  tabIndex={-1}
                  className={cn(
                    'flex cursor-pointer items-center justify-between gap-2 rounded-chip px-2 py-1.5 text-body',
                    index === active ? 'bg-accent-soft text-ink' : 'text-text',
                  )}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseDown={(event) => {
                    // Клик не должен уводить фокус из поиска раньше выбора
                    event.preventDefault()
                    select(item.value)
                  }}
                >
                  <span>{item.label}</span>
                  {item.value === value ? <Check aria-hidden="true" size={14} /> : null}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
