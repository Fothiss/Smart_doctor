import { Link, useLocation } from 'react-router-dom'

import type { Guideline } from '../api/guidelines'
import { formatDateTime, formatSize } from '../lib/format'
import type { DeletePhase } from '../store/deleteGuideline'
import { describeProgress, describeVectorization } from '../store/indexingStatus'
import { StatusBadge } from './StatusBadge'
import styles from './GuidelineRow.module.css'

export type GuidelineRowProps = {
  guideline: Guideline
  /** Повторить индексацию; для остальных статусов действие не предлагается. */
  onRetry?: (guidelineId: string) => void
  /** Идёт запрос повтора: кнопка блокируется, чтобы не запускать второй. */
  isRetrying?: boolean
  /** Запросить удаление: покажет подтверждение, но ничего не отправит. */
  onRequestDelete?: (guidelineId: string) => void
  /** Подтвердить удаление. */
  onConfirmDelete?: (guidelineId: string) => void
  /** Отменить удаление или скрыть причину отказа. */
  onCancelDelete?: (guidelineId: string) => void
  /** Фаза удаления именно этой строки. */
  deletePhase?: DeletePhase
  /** Причина отказа удаления именно этой строки. */
  deleteError?: string | null
}

/**
 * Строка списка библиотеки.
 *
 * Компонент презентационный: статус, ход обработки, признак векторизации и коды МКБ берутся из
 * метаданных сервера, а действия — колбэки снаружи. Подтверждение удаления — состояние строки,
 * поэтому его видно в разметке, а не в окне браузера.
 */
export function GuidelineRow({
  guideline,
  onRetry,
  isRetrying = false,
  onRequestDelete,
  onConfirmDelete,
  onCancelDelete,
  deletePhase = 'idle',
  deleteError = null,
}: GuidelineRowProps) {
  const location = useLocation()
  const progress = describeProgress(guideline)
  const vectorization = describeVectorization(guideline)
  const canRetry = guideline.status === 'failed' && onRetry !== undefined
  const codes = guideline.icd_codes ?? []

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
        {codes.length === 0 ? (
          <span className={styles.icdMissing}>коды МКБ не указаны</span>
        ) : (
          <span className={styles.icd}>
            {codes.map((code) => (
              <span key={code} className={styles.icdCode}>
                {code}
              </span>
            ))}
          </span>
        )}
        {progress === null ? null : (
          <span className={styles.progress} role="status">
            {progress}
          </span>
        )}
        {vectorization === null ? null : <span className={styles.vectorized}>{vectorization}</span>}
        {guideline.status === 'failed' && guideline.error != null ? (
          <span className={styles.error}>{guideline.error}</span>
        ) : null}
        {deleteError === null ? null : <span className={styles.error}>{deleteError}</span>}
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
        {renderDelete()}
        <StatusBadge status={guideline.status} />
      </div>
    </li>
  )

  function renderDelete() {
    if (onRequestDelete === undefined) {
      return null
    }
    if (deletePhase === 'confirming') {
      return (
        <>
          <span className={styles.confirmText}>Удалить клинрек?</span>
          <button
            type="button"
            className={styles.danger}
            onClick={() => onConfirmDelete?.(guideline.guideline_id)}
          >
            Подтвердить
          </button>
          <button type="button" onClick={() => onCancelDelete?.(guideline.guideline_id)}>
            Отмена
          </button>
        </>
      )
    }
    if (deletePhase === 'deleting') {
      return (
        <button type="button" disabled>
          Удаляем…
        </button>
      )
    }
    if (deletePhase === 'error') {
      return (
        <button type="button" onClick={() => onCancelDelete?.(guideline.guideline_id)}>
          Закрыть
        </button>
      )
    }
    return (
      <button
        type="button"
        className={styles.danger}
        onClick={() => onRequestDelete(guideline.guideline_id)}
      >
        Удалить
      </button>
    )
  }
}
