import { Link, useLocation } from 'react-router-dom'

import type { Guideline } from '../api/guidelines'
import { formatDateTime, formatSize } from '../lib/format'
import { StatusBadge } from './StatusBadge'
import styles from './GuidelineRow.module.css'

/** Строка списка библиотеки: название, файл, размер, дата загрузки и статус. */
export function GuidelineRow({ guideline }: { guideline: Guideline }) {
  const location = useLocation()

  return (
    <li className={styles.row}>
      <div className={styles.main}>
        <Link
          className={styles.title}
          to={`/library/${guideline.guideline_id}/view`}
          // Состояние списка уезжает в просмотрщик, чтобы возврат не потерял фильтр и страницы
          state={{ from: `/library${location.search}` }}
        >
          {guideline.title}
        </Link>
        <span className={styles.meta}>
          {guideline.filename} · {formatSize(guideline.size_bytes)} ·{' '}
          {formatDateTime(guideline.created_at)} · версия {guideline.version}
        </span>
        {guideline.status === 'failed' && guideline.error != null ? (
          <span className={styles.error}>{guideline.error}</span>
        ) : null}
      </div>
      <StatusBadge status={guideline.status} />
    </li>
  )
}
