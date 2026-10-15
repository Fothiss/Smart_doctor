import { Link, useLocation } from 'react-router-dom'

import type { Guideline } from '../api/guidelines'
import { formatDateTime, formatSize } from '../lib/format'
import { describeProgress, describeVectorization } from '../store/indexingStatus'
import { StatusBadge } from './StatusBadge'
import styles from './GuidelineRow.module.css'

export type GuidelineRowProps = {
  guideline: Guideline
  /** Повторить индексацию; для остальных статусов действие не предлагается. */
  onRetry?: (guidelineId: string) => void
  /** Идёт запрос повтора: кнопка блокируется, чтобы не запускать второй. */
  isRetrying?: boolean
}

/**
 * Строка списка библиотеки.
 *
 * Компонент презентационный: статус, ход обработки и признак векторизации берутся из
 * метаданных сервера, а повтор индексации — колбэк снаружи. Признак векторизации
 * показывается только для `ready`: обещать готовность раньше сервера нельзя.
 */
export function GuidelineRow({ guideline, onRetry, isRetrying = false }: GuidelineRowProps) {
  const location = useLocation()
  const progress = describeProgress(guideline)
  const vectorization = describeVectorization(guideline)
  const canRetry = guideline.status === 'failed' && onRetry !== undefined

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
        {progress === null ? null : (
          <span className={styles.progress} role="status">
            {progress}
          </span>
        )}
        {vectorization === null ? null : <span className={styles.vectorized}>{vectorization}</span>}
        {guideline.status === 'failed' && guideline.error != null ? (
          <span className={styles.error}>{guideline.error}</span>
        ) : null}
      </div>
      <div className={styles.actions}>
        {canRetry ? (
          <button
            type="button"
            onClick={() => onRetry(guideline.guideline_id)}
            disabled={isRetrying}
          >
            {isRetrying ? 'Запускаем…' : 'Повторить'}
          </button>
        ) : null}
        <StatusBadge status={guideline.status} />
      </div>
    </li>
  )
}
