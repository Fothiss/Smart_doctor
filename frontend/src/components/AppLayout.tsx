import { Link, NavLink, Outlet } from 'react-router-dom'

import { cn } from './ui/cn'

/** Общая рамка приложения: шапка с названием, переходы и область текущего экрана. */
export function AppLayout() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-[1180px] flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
          <Link to="/library" className="text-lead font-semibold tracking-tight text-ink no-underline">
            Smart Doctor
          </Link>

          <nav className="flex items-center gap-1 text-caption" aria-label="Основная навигация">
            <AppNavLink to="/library">Библиотека</AppNavLink>
            <AppNavLink to="/protocol/new">Новый протокол</AppNavLink>
            <AppNavLink to="/chat">Чат</AppNavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-[1180px] flex-1 flex-col px-6 py-6">
        <Outlet />
      </main>
    </div>
  )
}

/** Переход в шапке: текущий раздел подчёркнут фоном, а не только цветом. */
function AppNavLink({ to, children }: { to: string; children: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          'rounded-chip px-2 py-1 no-underline',
          isActive ? 'bg-accent-soft text-accent' : 'text-text-muted hover:text-accent',
        )
      }
    >
      {children}
    </NavLink>
  )
}
