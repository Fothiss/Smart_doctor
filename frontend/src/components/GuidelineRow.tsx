import { Link, useLocation } from 'react-router-dom'

import type { Guideline } from '../api/guidelines'
import { formatDateTime, formatSize } from '../lib/format'
import type { DeletePhase } from '../store/deleteGuideline'
import {
  describeProgress,
  describeVectorization,
  indexingPercent,
} from '../store/indexingStatus'
import { StatusBadge } from './StatusBadge'
import { Button } from './ui/Button'
import { Dialog } from './ui/Dialog'
import { Mono } from './ui/Typography'
import { cn } from './ui/cn'

export type GuidelineRowProps = {
  guideline: Guideline
  /** Номер строки в списке: моноширинный желоб слева, начиная с 1. */
  index?: number
  /** Повторить индексацию; для остальных статусов действие не предлагается. */
  onRetry?: (guidelineId: string) => void
  /** Идёт запрос повтора: кнопка блокируется, чтобы не запускать второй. */
  isRetrying?: boolean
  /** Запросить удаление: покажет диалог подтверждения, но ничего не отправит. */
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
 * метаданных сервера, действия — колбэки снаружи. Подтверждение удаления вынесено в диалог:
 * строка остаётся списком, а необратимое действие требует отдельного решения.
 *
 * Действия в покое показаны компактно, но остаются доступными при наведении, фокусе и на
 * устройствах без указателя.
 */
export function GuidelineRow({
  guideline,
  index,
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
  const percent = indexingPercent(guideline)
  const vectorization = describeVectorization(guideline)
  const canRetry = guideline.status === 'failed' && onRetry !== undefined
  const codes = guideline.icd_codes ?? []
  const isConfirming = deletePhase === 'confirming'
  const isDeleting = deletePhase === 'deleting'

  return (
    <li className="group flex flex-col gap-3 border-b border-border py-4 last:border-b-0 sm:flex-row sm:items-start sm:gap-4">
      {index === undefined ? null : (
        <Mono className="hidden w-7 shrink-0 pt-1 text-text-faint sm:block">
          {String(index).padStart(2, '0')}
        </Mono>
      )}

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <Link
          className="text-lead font-medium text-ink no-underline hover:underline"
          to={`/library/${guideline.guideline_id}/view`}
          // Состояние списка уезжает в просмотрщик, чтобы возврат не потерял фильтр и страницы
          state={{ from: `/library${location.search}` }}
        >
          {guideline.title}
        </Link>

        <p className="text-caption text-text-muted">
          {guideline.filename} · {formatSize(guideline.size_bytes)} ·{' '}
          {formatDateTime(guideline.created_at)} · версия {guideline.version}
        </p>

        {codes.length === 0 ? (
          <p className="text-caption text-text-muted">коды МКБ не указаны</p>
        ) : (
          <ul className="flex flex-wrap gap-1">
            {codes.map((code) => (
              <li key={code}>
                <Mono className="rounded-chip bg-accent-soft px-2 py-0.5 text-text">{code}</Mono>
              </li>
            ))}
          </ul>
        )}

        {progress === null ? null : (
          <div className="flex flex-col gap-1" role="status">
            <p className="text-caption text-text-muted">{progress}</p>
            {percent === null ? null : (
              <div
                className="h-1 w-40 overflow-hidden rounded-pill bg-surface-sunken"
                role="progressbar"
                aria-valuenow={percent}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Ход индексации"
              >
                <div className="h-full bg-accent" style={{ width: `${percent}%` }} />
              </div>
            )}
          </div>
        )}

        {vectorization === null ? null : (
          <p className="text-caption text-text-muted">{vectorization}</p>
        )}

        {guideline.status === 'failed' && guideline.error != null ? (
          <p className="text-caption text-danger">{guideline.error}</p>
        ) : null}
        {deleteError === null ? null : <p className="text-caption text-danger">{deleteError}</p>}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {deletePhase === 'error' ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCancelDelete?.(guideline.guideline_id)}
          >
            Закрыть
          </Button>
        ) : null}
        <div
          className={cn(
            'flex items-center gap-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100',
            '[@media(hover:none)]:opacity-100',
          )}
        >
          {canRetry ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onRetry(guideline.guideline_id)}
              disabled={isRetrying}
            >
              {isRetrying ? 'Запускаем…' : 'Повторить'}
            </Button>
          ) : null}
          {onRequestDelete === undefined ? null : (
            <Button
              variant="danger"
              size="sm"
              onClick={() => onRequestDelete(guideline.guideline_id)}
            >
              Удалить
            </Button>
          )}
        </div>
        <StatusBadge status={guideline.status} />
      </div>

      {onRequestDelete === undefined ? null : (
        <Dialog
          open={isConfirming || isDeleting}
          onOpenChange={(open) => {
            if (!open) {
              onCancelDelete?.(guideline.guideline_id)
            }
          }}
          title="Удалить клинрек?"
          description={`${guideline.title} и все его фрагменты исчезнут из библиотеки. Действие необратимо.`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="danger"
              onClick={() => onConfirmDelete?.(guideline.guideline_id)}
              disabled={isDeleting}
            >
              {isDeleting ? 'Удаляем…' : 'Подтвердить'}
            </Button>
            <Button onClick={() => onCancelDelete?.(guideline.guideline_id)} disabled={isDeleting}>
              Отмена
            </Button>
          </div>
        </Dialog>
      )}
    </li>
  )
}
