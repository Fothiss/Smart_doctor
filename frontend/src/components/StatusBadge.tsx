import { GUIDELINE_STATUS_LABELS, type GuidelineStatus } from '../api/guidelines'
import styles from './StatusBadge.module.css'

const STATUS_CLASS: Record<GuidelineStatus, string> = {
  uploaded: styles.uploaded,
  processing: styles.processing,
  ready: styles.ready,
  failed: styles.failed,
}

/**
 * Статус клинрека.
 *
 * Текст и цвет идут вместе: один цвет статус не кодирует. Подпись берётся из фактического
 * значения сервера, поэтому `uploaded` не выглядит как готовность к проверке.
 */
export function StatusBadge({ status }: { status: GuidelineStatus }) {
  return <span className={`${styles.badge} ${STATUS_CLASS[status]}`}>{GUIDELINE_STATUS_LABELS[status]}</span>
}
