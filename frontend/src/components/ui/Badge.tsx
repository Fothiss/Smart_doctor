import { cva, type VariantProps } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'

import { cn } from './cn'

/**
 * Метка состояния: текст всегда есть, цвет только усиливает его.
 *
 * Тона повторяют статусы клинрека (`uploaded | processing | ready | failed`) и общие случаи —
 * «акцент» и «подсветка источника». Пары «фон + текст + рамка» заданы токенами для каждой темы
 * отдельно: полупрозрачная заливка делала бы контраст зависимым от подложки.
 */
const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-caption font-semibold ring-1 ring-inset',
  {
    variants: {
      tone: {
        neutral: 'bg-status-uploaded-bg text-status-uploaded-fg ring-status-uploaded-border',
        processing: 'bg-status-processing-bg text-status-processing-fg ring-status-processing-border',
        ready: 'bg-status-ready-bg text-status-ready-fg ring-status-ready-border',
        failed: 'bg-status-failed-bg text-status-failed-fg ring-status-failed-border',
        accent: 'bg-accent-soft text-accent ring-status-ready-border',
        mark: 'bg-mark text-mark-ink ring-mark-border',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
