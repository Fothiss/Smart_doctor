import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/**
 * Заполнитель будущего содержимого.
 *
 * Показывает структуру списка, чтобы появление данных не сдвигало вёрстку. Пульсация берётся из
 * шкалы движения (`animate-pulse-soft`), поэтому при уменьшении движения её гасит базовый слой,
 * а не собственные значения компонента.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse-soft rounded-chip bg-surface-sunken', className)}
      {...props}
    />
  )
}

/** Заполнитель строки списка: желоб, заголовок, мета, метка статуса — в форме карточки. */
export function SkeletonRow() {
  return (
    <div className="flex items-start gap-4 rounded-card border border-border bg-surface p-4">
      <Skeleton className="mt-1 h-3 w-6 shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-4 w-20" />
      </div>
      <Skeleton className="h-5 w-24 shrink-0" />
    </div>
  )
}

/** Список заполнителей для состояния загрузки. */
export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div role="status" aria-label="Загружаем список" className="flex flex-col gap-2">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonRow key={index} />
      ))}
    </div>
  )
}
