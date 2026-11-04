import { type ClassValue, clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/** Имена наших цветовых токенов: без них `tailwind-merge` не увидит конфликт классов. */
const COLORS = [
  'bg',
  'surface',
  'surface-raised',
  'surface-sunken',
  'border',
  'border-strong',
  'text',
  'text-muted',
  'text-faint',
  'ink',
  'accent',
  'accent-hover',
  'accent-text',
  'accent-soft',
  'accent-2',
  'mark',
  'mark-border',
  'mark-soft',
  'mark-ink',
  'danger',
  'danger-bg',
  'scrim',
  'glass',
  'status-uploaded-bg',
  'status-uploaded-fg',
  'status-uploaded-border',
  'status-processing-bg',
  'status-processing-fg',
  'status-processing-border',
  'status-ready-bg',
  'status-ready-fg',
  'status-ready-border',
  'status-failed-bg',
  'status-failed-fg',
  'status-failed-border',
] as const

/**
 * `tailwind-merge` не знает наших токенов, поэтому `text-danger` и `text-body` попали бы в одну
 * группу и один из классов пропал бы. Регистрируем имена токенов явно — по всем группам, где
 * экран перекрывает вариант компонента.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-family': [{ font: ['sans', 'display', 'mono'] }],
      'font-size': [
        { text: ['overline', 'caption', 'body', 'lead', 'h3', 'h2', 'h1', 'display'] },
      ],
      'text-color': [{ text: [...COLORS] }],
      'bg-color': [{ bg: [...COLORS] }],
      'border-color': [{ border: [...COLORS] }],
      'ring-color': [{ ring: [...COLORS] }],
    },
  },
})

/**
 * Склейка классов: `clsx` собирает условные классы, `tailwind-merge` снимает конфликты,
 * чтобы внешний `className` перебивал вариант компонента, а не дублировал его.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
