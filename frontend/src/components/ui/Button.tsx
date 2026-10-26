import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'

import { cn } from './cn'

/**
 * Варианты кнопки.
 *
 * Оформление браузера по умолчанию не используется нигде: даже призрачное действие имеет
 * собственные состояния. Цвета берутся только из токенов.
 */
const buttonVariants = cva(
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-chip font-medium ' +
    'cursor-pointer disabled:cursor-default disabled:opacity-55',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-text hover:bg-accent-hover',
        secondary:
          'border border-border-strong bg-surface text-text hover:border-accent hover:text-accent',
        ghost: 'text-accent hover:bg-accent-soft',
        danger: 'text-danger hover:bg-danger-bg',
      },
      size: {
        sm: 'h-7 px-2 text-caption',
        md: 'h-9 px-3 text-body',
      },
    },
    defaultVariants: {
      variant: 'secondary',
      size: 'md',
    },
  },
)

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>

/** Кнопка действия: единственный способ нарисовать кнопку в приложении. */
export function Button({ className, variant, size, type = 'button', ...props }: ButtonProps) {
  return (
    <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
}
