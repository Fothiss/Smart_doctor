import * as Popover from '@radix-ui/react-popover'
import { Check, Monitor, Moon, Sun } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { cn } from './cn'
import {
  type ResolvedTheme,
  type ThemePreference,
  applyTheme,
  readThemePreference,
  resolveTheme,
  systemPrefersDark,
  writeThemePreference,
} from './theme'

type ThemeOption = {
  value: ThemePreference
  label: string
  description: string
  Icon: typeof Sun
}

/** Три состояния, а не переключатель на два: к системной настройке нужно уметь вернуться. */
const OPTIONS: readonly ThemeOption[] = [
  { value: 'system', label: 'Системная', description: 'Как в системе', Icon: Monitor },
  { value: 'light', label: 'Светлая', description: 'Всегда светлая', Icon: Sun },
  { value: 'dark', label: 'Тёмная', description: 'Всегда тёмная', Icon: Moon },
]

/**
 * Текущая тема и способ её сменить.
 *
 * Живёт рядом с переключателем, а не в `store/`: это оформление, а не состояние данных. Выбор
 * хранится в `localStorage`, системная настройка отслеживается на лету — переключение темы в ОС
 * меняет оформление, пока пользователь не выбрал режим вручную.
 */
export function useTheme(): {
  preference: ThemePreference
  theme: ResolvedTheme
  setPreference: (next: ThemePreference) => void
} {
  const [preference, setPreferenceState] = useState<ThemePreference>(readThemePreference)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return
    }
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (): void => setSystemDark(query.matches)
    query.addEventListener('change', handleChange)
    return () => query.removeEventListener('change', handleChange)
  }, [])

  const theme = resolveTheme(preference, systemDark)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setPreference = useCallback((next: ThemePreference) => {
    writeThemePreference(next)
    setPreferenceState(next)
  }, [])

  return { preference, theme, setPreference }
}

/**
 * Переключатель темы в шапке.
 *
 * Меню, а не тумблер: двухпозиционный переключатель не даёт вернуться к системной настройке,
 * а именно она стоит по умолчанию. Собрано на уже подключённом Radix Popover — новых
 * зависимостей ради меню не появляется.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { preference, theme, setPreference } = useTheme()
  const TriggerIcon = theme === 'dark' ? Moon : Sun

  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label={`Оформление: ${theme === 'dark' ? 'тёмная' : 'светлая'} тема`}
        className={cn(
          'flex size-8 cursor-pointer items-center justify-center rounded-chip text-text-muted',
          'hover:bg-surface-sunken hover:text-ink',
          className,
        )}
      >
        <TriggerIcon aria-hidden="true" size={16} />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          align="end"
          className="z-50 w-60 animate-pop rounded-card border border-border bg-surface-raised p-1 shadow-panel"
        >
          <p className="px-2 py-1 text-overline font-semibold tracking-[0.08em] text-text-muted uppercase">
            Оформление
          </p>
          <div role="group" aria-label="Тема оформления" className="flex flex-col">
            {OPTIONS.map(({ value, label, description, Icon }) => {
              const isActive = preference === value
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => setPreference(value)}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-chip px-2 py-1.5 text-left text-body',
                    isActive ? 'bg-accent-soft text-ink' : 'text-text hover:bg-surface-sunken',
                  )}
                >
                  <Icon aria-hidden="true" size={15} className="shrink-0 text-text-muted" />
                  <span className="flex min-w-0 flex-col">
                    <span className="font-medium">{label}</span>
                    <span className="text-caption text-text-muted">{description}</span>
                  </span>
                  {isActive ? <Check aria-hidden="true" size={14} className="ml-auto shrink-0" /> : null}
                </button>
              )
            })}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
