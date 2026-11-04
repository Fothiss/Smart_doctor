import { Link } from 'react-router-dom'

import { LogoMark } from '../components/ui/Logo'
import { Overline } from '../components/ui/Typography'

/** Экран неизвестного адреса: объясняет, что произошло, и возвращает в библиотеку. */
export function NotFoundPage() {
  return (
    <section className="flex animate-rise flex-col items-start gap-3 py-8">
      <span className="flex size-12 items-center justify-center rounded-panel border border-border bg-surface text-accent shadow-card">
        <LogoMark size={22} />
      </span>
      <Overline>Ошибка адреса</Overline>
      <h1>Страница не найдена</h1>
      <p className="text-body text-text-muted">
        Такого экрана нет. <Link to="/library">Вернуться в библиотеку</Link>
      </p>
    </section>
  )
}
