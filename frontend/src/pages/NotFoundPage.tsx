import { Link } from 'react-router-dom'

/** Экран неизвестного адреса. */
export function NotFoundPage() {
  return (
    <section>
      <h1>Страница не найдена</h1>
      <p>
        Такого экрана нет. <Link to="/library">Вернуться в библиотеку</Link>
      </p>
    </section>
  )
}
