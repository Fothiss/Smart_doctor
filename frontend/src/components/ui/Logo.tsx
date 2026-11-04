import { cn } from './cn'

export type LogoMarkProps = {
  /** Размер знака в пикселях: 24 в шапке, 16 — то, что должно читаться в favicon. */
  size?: number
  className?: string
}

/**
 * Знак продукта: две скобки-«фрагмент» и точка-источник между ними.
 *
 * Форма буквально повторяет инвариант системы — вердикт всегда указывает на конкретный чанк
 * клинрека. Рисуется `currentColor`, поэтому живёт на токенах и в обеих темах, без отдельного
 * ассета под каждую тему.
 */
export function LogoMark({ size = 24, className }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={cn('shrink-0', className)}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M7.5 3.5H5.2a1.2 1.2 0 0 0-1.2 1.2v14.6a1.2 1.2 0 0 0 1.2 1.2h2.3" />
      <path d="M16.5 3.5h2.3a1.2 1.2 0 0 1 1.2 1.2v14.6a1.2 1.2 0 0 1-1.2 1.2h-2.3" />
      <circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none" />
    </svg>
  )
}

export type LogoProps = {
  /** Показать название рядом со знаком. Без названия знак не используется как указатель раздела. */
  withWordmark?: boolean
  size?: number
  className?: string
}

/** Бренд: знак и название. Название набрано display-начертанием — только оно и заголовки экранов. */
export function Logo({ withWordmark = true, size = 24, className }: LogoProps) {
  return (
    <span className={cn('flex items-center gap-2 text-accent', className)}>
      <LogoMark size={size} />
      {withWordmark ? (
        <span className="font-display text-body font-semibold tracking-[-0.02em] text-ink">
          Smart Doctor
        </span>
      ) : null}
    </span>
  )
}
