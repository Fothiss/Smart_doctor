import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/** Надзаголовок раздела: мелкие прописные с разрядкой, без смысловой нагрузки. */
export function Overline({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        'text-overline font-semibold uppercase tracking-[0.08em] text-text-muted',
        className,
      )}
      {...props}
    />
  )
}

/** Код или число: моноширинное начертание с выровненными разрядами. */
export function Mono({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn('font-mono text-caption tabular-nums', className)} {...props} />
}
