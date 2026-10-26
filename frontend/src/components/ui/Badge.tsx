import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/**
 * Метка состояния: текст всегда есть, цвет только усиливает его.
 *
 * Тона повторяют статусы клинрека (`uploaded | processing | ready | failed`) и общие
 * случаи — «внимание» и «опасность». Внутренняя рамка отделяет метку от фона при
 * насыщенных оттенках и не добавляет второго цвета.
 */
const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-caption font-semibold ring-1 ring-inset',
  {
    variants: {
      tone: {
        neutral:
          'bg-[var(--status-uploaded-bg)] text-[var(--status-uploaded-fg)] ring-[var(--status-uploaded-border)]',
        processing:
          'bg-[var(--status-processing-bg)] text-[var(--status-processing-fg)] ring-[var(--status-processing-border)]',
        ready:
          'bg-[var(--status-ready-bg)] text-[var(--status-ready-fg)] ring-[var(--status-ready-border)]',
        failed:
          'bg-[var(--status-failed-bg)] text-[var(--status-failed-fg)] ring-[var(--status-failed-border)]',
        accent: 'bg-accent-soft text-accent ring-[var(--status-ready-border)]',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
