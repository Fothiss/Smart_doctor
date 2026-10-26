import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/**
 * Заполнитель будущего содержимого.
 *
 * Показывает структуру списка, чтобы появление данных не сдвигало вёрстку. При включённом
 * уменьшении движения пульсация отключается базовым слоем.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-chip bg-surface-sunken', className)}
      {...props}
    />
  )
}

/** Заполнитель строки списка: желоб, заголовок, мета, метка статуса. */
export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 border-b border-border py-4">
      <Skeleton className="h-3 w-6" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-5 w-24" />
    </div>
  )
}

/** Список заполнителей для состояния загрузки. */
export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div role="status" aria-label="Загружаем список">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonRow key={index} />
      ))}
    </div>
  )
}
