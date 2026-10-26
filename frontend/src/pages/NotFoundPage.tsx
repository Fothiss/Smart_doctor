import { Link } from 'react-router-dom'

import { Overline } from '../components/ui/Typography'

/** Экран неизвестного адреса. */
export function NotFoundPage() {
  return (
    <section className="flex flex-col gap-2">
      <Overline>Ошибка адреса</Overline>
      <h1>Страница не найдена</h1>
      <p className="text-body text-text-muted">
        Такого экрана нет. <Link to="/library">Вернуться в библиотеку</Link>
      </p>
    </section>
  )
}
