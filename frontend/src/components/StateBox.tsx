import type { ReactNode } from 'react'

import styles from './StateBox.module.css'

export type StateBoxKind = 'loading' | 'empty' | 'error'

export type StateBoxProps = {
  kind: StateBoxKind
  title: string
  description?: string
  action?: ReactNode
}

/**
 * Блок состояния экрана: загрузка, пустой результат или ошибка.
 *
 * Пустой список и ошибка выглядят по-разному: пустое хранилище не должно читаться как сбой.
 */
export function StateBox({ kind, title, description, action }: StateBoxProps) {
  const className = kind === 'error' ? `${styles.box} ${styles.error}` : styles.box

  return (
    <div className={className} role={kind === 'error' ? 'alert' : 'status'}>
      <p className={styles.title}>{title}</p>
      {description === undefined ? null : <p className={styles.description}>{description}</p>}
      {action === undefined ? null : <div className={styles.action}>{action}</div>}
    </div>
  )
}
