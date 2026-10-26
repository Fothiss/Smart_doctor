import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/** Поверхность карточки: одна тень на всё приложение, объём даёт бумага, а не свечение. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-card border border-border bg-surface shadow-card',
        className,
      )}
      {...props}
    />
  )
}
