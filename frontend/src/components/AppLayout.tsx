import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'

import { Logo } from './ui/Logo'
import { ThemeToggle } from './ui/ThemeToggle'
import { cn } from './ui/cn'

/** Разделы приложения: порядок совпадает с рабочим сценарием — от библиотеки к чату. */
const NAV = [
  { to: '/library', label: 'Библиотека' },
  { to: '/protocol/new', label: 'Новый протокол' },
  { to: '/chat', label: 'Чат' },
] as const

/**
 * Общая рамка приложения: строка бренда с утилитами и сегментированная навигация разделов.
 *
 * Сегменты — это навигация, а не табы: переход меняет адрес и перерисовывает панель целиком,
 * поэтому ссылки получают `aria-current="page"` от `NavLink`, а не `role="tab"`. Шапка липкая и
 * стеклянная настолько, чтобы длинный список не уносил навигацию с экрана.
 *
 * `fullBleed` — вариант для просмотрщика: страница документа получает всю ширину, шапка остаётся
 * на месте, поэтому выход в библиотеку не теряется.
 */
export function AppLayout({ fullBleed = false }: { fullBleed?: boolean }) {
  // Смена экрана сопровождается одним переходом: ключ по адресу перезапускает анимацию
  const { pathname } = useLocation()

  return (
    <div className="flex min-h-full flex-col">
      <header className="glass sticky top-0 z-30 border-b border-border">
        <div className="mx-auto flex w-full max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-1 px-5 pt-2.5">
          <Link to="/library" className="rounded-chip no-underline">
            <Logo />
          </Link>

          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
          </div>
        </div>

        <nav
          aria-label="Основная навигация"
          className="mx-auto w-full max-w-[1320px] px-5 py-2"
        >
          <div className="inline-flex items-center gap-1 rounded-pill border border-border bg-surface-sunken p-1">
            {NAV.map((item) => (
              <AppNavLink key={item.to} to={item.to}>
                {item.label}
              </AppNavLink>
            ))}
          </div>
        </nav>
      </header>

      <main
        key={pathname}
        className={cn(
          'mx-auto flex min-h-0 w-full animate-fade-in flex-col',
          fullBleed ? 'max-w-none flex-1 px-0 py-0' : 'max-w-[1320px] flex-1 px-5 py-6',
        )}
      >
        <Outlet />
      </main>
    </div>
  )
}

/** Переход в шапке: текущий раздел отличается поверхностью, а не только цветом текста. */
function AppNavLink({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'rounded-pill px-3 py-1 text-caption font-medium no-underline',
          isActive
            ? 'bg-surface text-ink shadow-card'
            : 'text-text-muted hover:bg-surface hover:text-ink',
        )
      }
    >
      {children}
    </NavLink>
  )
}
