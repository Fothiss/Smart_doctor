import type { ReactNode } from 'react'

import { cn } from './cn'

/** Свойства, которые поле передаёт своему контролу. */
export type FieldControlProps = {
  id: string
  'aria-invalid': boolean
  'aria-describedby': string | undefined
}

export type FieldProps = {
  /** Идентификатор контрола: связывает подпись, подсказку и ошибку с полем. */
  id: string
  label: string
  hint?: string
  error?: string | null
  className?: string
  /** Контрол получает готовые `id`, `aria-invalid` и `aria-describedby`. */
  children: (props: FieldControlProps) => ReactNode
}

/**
 * Поле формы: подпись, подсказка и ошибка рядом с контролом.
 *
 * Ошибка связана с полем программно, поэтому вспомогательные технологии читают её вместе с полем,
 * а не как отдельное сообщение где-то в конце формы.
 */
export function Field({ id, label, hint, error, className, children }: FieldProps) {
  const hintId = hint === undefined ? undefined : `${id}-hint`
  const errorId = error === null || error === undefined ? undefined : `${id}-error`
  const describedBy = [errorId, hintId].filter((value) => value !== undefined).join(' ')

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-caption text-text-muted">
        {label}
      </label>
      {children({
        id,
        'aria-invalid': errorId !== undefined,
        'aria-describedby': describedBy === '' ? undefined : describedBy,
      })}
      {errorId === undefined ? null : (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      )}
      {hintId === undefined ? null : (
        <p id={hintId} className="text-caption text-text-muted">
          {hint}
        </p>
      )}
    </div>
  )
}

/**
 * Классы полей ввода: одинаковые во всех формах.
 *
 * Цвет рамки задаёт `field-control` из базового слоя: невалидность и фокус — его состояния,
 * поэтому вокруг поля не появляется двух обводок одновременно.
 */
export const controlClassName =
  'field-control w-full rounded-chip border bg-surface px-2 py-1.5 text-body text-text ' +
  'placeholder:text-text-faint'
