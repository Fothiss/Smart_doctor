import { ArrowUp } from 'lucide-react'
import { type KeyboardEvent, useEffect, useRef } from 'react'

import { Button } from '../ui/Button'
import { cn } from '../ui/cn'

export type ChatComposerProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  disabled: boolean
  pending: boolean
  /** Подсказка под полем: что мешает отправить вопрос. */
  hint?: string
  placeholder?: string
}

/**
 * Поле вопроса внизу чата.
 *
 * Enter отправляет, Shift+Enter переносит строку — как в знакомых чатах: набирать вопрос
 * в три строки через Ctrl+Enter никто не ожидает, а случайная отправка на переносе строки
 * раздражает больше, чем помогает.
 */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  pending,
  hint,
  placeholder = 'Спросите про лечение, диагностику или дозировки…',
}: ChatComposerProps) {
  const fieldRef = useRef<HTMLTextAreaElement>(null)

  // Поле растёт под текст: длинный вопрос не должен прятаться за прокруткой в две строки
  useEffect(() => {
    const field = fieldRef.current
    if (field === null) {
      return
    }
    field.style.height = 'auto'
    field.style.height = `${Math.min(field.scrollHeight, 200)}px`
  }, [value])

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (!disabled) {
        onSubmit()
      }
    }
  }

  return (
    <form
      className="flex flex-col gap-1"
      onSubmit={(event) => {
        event.preventDefault()
        if (!disabled) {
          onSubmit()
        }
      }}
    >
      <div className="flex items-end gap-2 rounded-panel border border-border-strong bg-surface p-2 shadow-card focus-within:border-accent">
        <label htmlFor="chat-question" className="sr-only">
          Вопрос по клинрекам
        </label>
        <textarea
          id="chat-question"
          ref={fieldRef}
          rows={1}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          className={cn(
            'max-h-[200px] min-h-[2.25rem] flex-1 resize-none border-0 bg-transparent px-1 py-1.5',
            'text-body text-text placeholder:text-text-faint focus:outline-none',
          )}
        />
        <Button
          type="submit"
          variant="primary"
          aria-label={pending ? 'Идёт поиск' : 'Отправить'}
          disabled={disabled}
          className="size-9 rounded-pill p-0"
        >
          <ArrowUp aria-hidden="true" size={18} />
        </Button>
      </div>
      <p className="px-1 text-caption text-text-faint">
        {hint ?? 'Enter — отправить, Shift+Enter — новая строка'}
      </p>
    </form>
  )
}
