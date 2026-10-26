import { GUIDELINE_STATUS_LABELS, type GuidelineStatus } from '../api/guidelines'
import { Badge, type BadgeProps } from './ui/Badge'

/** Тона метки по статусу: цвет усиливает текст, но не заменяет его. */
const STATUS_TONE: Record<GuidelineStatus, NonNullable<BadgeProps['tone']>> = {
  uploaded: 'neutral',
  processing: 'processing',
  ready: 'ready',
  failed: 'failed',
}

/**
 * Статус клинрека.
 *
 * Подпись берётся из фактического значения сервера: `uploaded` не выглядит как готовность
 * к проверке, пока индексация не перевела документ в `ready`.
 */
export function StatusBadge({ status }: { status: GuidelineStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]}>
      <span aria-hidden="true" className="size-1.5 rounded-pill bg-current" />
      {GUIDELINE_STATUS_LABELS[status]}
    </Badge>
  )
}
