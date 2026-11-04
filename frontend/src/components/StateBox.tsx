import type { ReactNode } from 'react'

import { cn } from './ui/cn'

export type StateBoxKind = 'loading' | 'empty' | 'error'

export type StateBoxProps = {
  kind: StateBoxKind
  title: string
  description?: string
  action?: ReactNode
}

/**
 * Блок состояния экрана: загрузка, пустой результат или ошибка.
 *
 * Пустой список и ошибка выглядят по-разному: пустое хранилище не должно читаться как сбой.
 * Появление блока анимируется тем же переходом, что и строки списка, — состояние не «прыгает».
 */
export function StateBox({ kind, title, description, action }: StateBoxProps) {
  const isError = kind === 'error'

  return (
    <div
      role={isError ? 'alert' : 'status'}
      className={cn(
        'flex animate-fade-in flex-col items-center gap-2 rounded-card border px-6 py-8 text-center',
        isError
          ? 'border-danger bg-danger-bg'
          : 'border-dashed border-border-strong bg-surface-sunken',
      )}
    >
      <p className={cn('text-h3 font-semibold', isError ? 'text-danger' : 'text-ink')}>{title}</p>
      {description === undefined ? null : (
        <p className="max-w-prose text-caption text-text-muted">{description}</p>
      )}
      {action === undefined ? null : <div className="mt-2">{action}</div>}
    </div>
  )
}
