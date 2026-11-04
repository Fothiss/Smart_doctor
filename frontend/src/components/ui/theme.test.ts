import { describe, expect, it } from 'vitest'

import { resolveTheme } from './theme'

/**
 * Правило выбора темы.
 *
 * `readThemePreference` и `writeThemePreference` намеренно не проверяются здесь: без окна они
 * вырождаются в константу, а их поведение покрыто DOM-тестом переключателя.
 */
describe('resolveTheme', () => {
  it('следует системной настройке, пока выбор не сделан', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
  })

  it('ручной выбор сильнее системной настройки', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })
})
