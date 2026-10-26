import { type ClassValue, clsx } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * `tailwind-merge` не знает наших токенов, поэтому `text-danger` и `text-body` попали бы в одну
 * группу и один из классов пропал бы. Регистрируем имена токенов явно.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [
        { text: ['overline', 'caption', 'body', 'lead', 'h3', 'h2', 'h1', 'display'] },
      ],
      'text-color': [
        { text: ['text', 'text-muted', 'text-faint', 'ink', 'accent', 'accent-text', 'danger'] },
      ],
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
