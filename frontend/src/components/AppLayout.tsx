import { Link, Outlet } from 'react-router-dom'

import styles from './AppLayout.module.css'

/** Общая рамка приложения: шапка с названием и область текущего экрана. */
export function AppLayout() {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link className={styles.brand} to="/library">
          Smart Doctor
        </Link>
        <span className={styles.tagline}>
          Проверка протоколов на соответствие клиническим рекомендациям
        </span>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
