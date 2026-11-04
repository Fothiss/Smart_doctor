/**
 * Режим оформления: чистая логика без React.
 *
 * Тема — это оформление, а не бизнес-состояние приложения, поэтому она живёт рядом с компонентом
 * переключателя, а не в `store/`. Функции отделены от хука, чтобы их можно было проверить тестом
 * без DOM и чтобы тот же расчёт повторил инлайн-скрипт в `index.html`.
 */

/** Что выбрал пользователь. `system` — следовать системной настройке. */
export type ThemePreference = 'system' | 'light' | 'dark'

/** Что в итоге применилось к документу. */
export type ResolvedTheme = 'light' | 'dark'

/** Ключ хранения выбора: тот же литерал продублирован в инлайн-скрипте `index.html`. */
export const THEME_STORAGE_KEY = 'smart-doctor-theme'

/** Цвет панели браузера: совпадает с фоном темы, чтобы адресная строка не спорила с экраном. */
const THEME_COLOR: Record<ResolvedTheme, string> = {
  light: '#f6f8fb',
  dark: '#0b1220',
}

function hasWindow(): boolean {
  return typeof window !== 'undefined'
}

/** Сохранённый выбор; незнакомое значение и недоступное хранилище читаются как `system`. */
export function readThemePreference(): ThemePreference {
  if (!hasWindow()) {
    return 'system'
  }
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
    return stored === 'light' || stored === 'dark' ? stored : 'system'
  } catch {
    // Приватный режим браузера: хранилище недоступно, но оформление работать должно
    return 'system'
  }
}

/** Запомнить выбор. `system` удаляет ключ, чтобы вернуться к поведению по умолчанию. */
export function writeThemePreference(preference: ThemePreference): void {
  if (!hasWindow()) {
    return
  }
  try {
    if (preference === 'system') {
      window.localStorage.removeItem(THEME_STORAGE_KEY)
    } else {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference)
    }
  } catch {
    // Не сохранилось — не повод ломать переключение: тема применится на текущую сессию
  }
}

/** Системная настройка; без `matchMedia` (jsdom, старые движки) считаем, что светлая. */
export function systemPrefersDark(): boolean {
  if (!hasWindow() || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** Итоговая тема: ручной выбор сильнее системной настройки. */
export function resolveTheme(
  preference: ThemePreference,
  systemDark: boolean,
): ResolvedTheme {
  if (preference === 'system') {
    return systemDark ? 'dark' : 'light'
  }
  return preference
}

/**
 * Применить тему к документу.
 *
 * `data-theme` читают токены оформления, `color-scheme` — нативные полосы прокрутки и контролы,
 * `theme-color` — панель браузера. Одной пары мета-тегов через `media` недостаточно: ручной выбор
 * сильнее системного, поэтому цвет панели обновляется здесь.
 */
export function applyTheme(theme: ResolvedTheme): void {
  if (!hasWindow()) {
    return
  }
  const root = document.documentElement
  root.dataset.theme = theme
  root.style.colorScheme = theme
  document.getElementById('theme-color')?.setAttribute('content', THEME_COLOR[theme])
}
