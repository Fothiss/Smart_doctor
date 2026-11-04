// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeToggle } from './ThemeToggle'
import { THEME_STORAGE_KEY } from './theme'

/**
 * Переключатель темы.
 *
 * jsdom не умеет `matchMedia`, поэтому системная настройка подменяется: тест проверяет именно
 * правило «ручной выбор сильнее системного» и сохранение выбора между сессиями.
 */
beforeEach(() => {
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

describe('ThemeToggle', () => {
  it('показывает три режима оформления', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: /Оформление/ }))

    expect(screen.getByRole('button', { name: /Системная/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Светлая/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Тёмная/ })).toBeTruthy()
  })

  it('ставит тёмную тему и запоминает выбор', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: /Оформление/ }))
    await user.click(screen.getByRole('button', { name: /Тёмная/ }))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
    expect(document.getElementById('theme-color')).toBeNull()
  })

  it('возвращает следование системной настройке и снимает сохранённый выбор', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: /Оформление/ }))
    await user.click(screen.getByRole('button', { name: /Системная/ }))

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })
})
