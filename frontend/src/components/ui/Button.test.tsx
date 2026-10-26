import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { Button } from './Button'

/** Разметка кнопки: классы проверяем как признак варианта, текст — как единственный носитель смысла. */
function render(props: Parameters<typeof Button>[0]): string {
  return renderToString(<Button {...props}>Удалить</Button>)
}

describe('Button', () => {
  it('передаёт текст и показывает основное действие акцентом', () => {
    const html = render({ variant: 'primary' })

    expect(html).toContain('Удалить')
    expect(html).toContain('bg-accent')
    expect(html).toContain('type="button"')
  })

  it('опасное действие отличается от второстепенного', () => {
    expect(render({ variant: 'danger' })).toContain('text-danger')
    expect(render({ variant: 'secondary' })).toContain('border-border-strong')
  })

  it('призрачное действие не рисует рамку', () => {
    const html = render({ variant: 'ghost' })

    expect(html).toContain('text-accent')
    expect(html).not.toContain('border-border-strong')
  })

  it('недоступная кнопка остаётся читаемой и не выглядит обычной', () => {
    const html = render({ variant: 'primary', disabled: true })

    expect(html).toContain('disabled')
    expect(html).toContain('disabled:opacity-55')
  })

  it('тип submit передаётся явно', () => {
    expect(render({ type: 'submit' })).toContain('type="submit"')
  })
})
