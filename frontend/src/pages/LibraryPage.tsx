import { type FormEvent, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { describeError } from '../api/client'
import {
  GUIDELINE_STATUSES,
  GUIDELINE_STATUS_LABELS,
  type GuidelineStatus,
  deleteGuideline,
  isGuidelineStatus,
} from '../api/guidelines'
import { GuidelineRow } from '../components/GuidelineRow'
import { StateBox } from '../components/StateBox'
import { UploadForm } from '../components/UploadForm'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { controlClassName } from '../components/ui/Field'
import { SkeletonRows } from '../components/ui/Skeleton'
import { Mono, Overline } from '../components/ui/Typography'
import { cn } from '../components/ui/cn'
import { useToast } from '../components/ui/Toast'
import { useGuidelineList } from '../hooks/useGuidelineList'
import { ICD_FORMAT_HINT, normalizeIcd } from '../lib/icd'
import {
  IDLE_DELETE,
  type DeleteState,
  cancelDelete,
  deletePhaseFor,
  hideGuideline,
  requestDelete,
  startDelete,
} from '../store/deleteGuideline'
import { selectListView } from '../store/listView'
import {
  readIcd,
  readOffset,
  readStatus,
  writeIcd,
  writeOffset,
  writeStatus,
} from '../store/urlParams'

/**
 * Экран библиотеки клинреков.
 *
 * Фильтры и позиция списка живут в адресе: возврат из просмотрщика восстанавливает список,
 * а ссылкой на отфильтрованную библиотеку можно поделиться.
 *
 * Удаление двухшаговое и необратимое: строка просит подтверждение диалогом, и только потом уходит
 * запрос. После успеха клинрек исчезает из списка без перезагрузки страницы.
 */
export function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = readStatus(searchParams)
  const icd = readIcd(searchParams)
  const notify = useToast()

  // Позиция для восстановления фиксируется на входе в экран: дальше догрузка идёт в состоянии хука
  const [restoreOffset, setRestoreOffset] = useState(() => readOffset(searchParams))

  const { items, isLoading, isLoadingMore, hasMore, error, loadMore, reload } = useGuidelineList(
    status,
    icd,
    restoreOffset,
  )

  const [deleteState, setDeleteState] = useState<DeleteState>(IDLE_DELETE)
  const [hiddenIds, setHiddenIds] = useState<readonly string[]>([])
  const [icdDraft, setIcdDraft] = useState(icd ?? '')
  const [isUploadOpen, setIsUploadOpen] = useState(false)

  const visibleItems = items.filter((item) => !hiddenIds.includes(item.guideline_id))
  const loadedOffset = readOffset(searchParams)
  const isEmptyLibrary =
    !isLoading && error === null && items.length === 0 && status === null && icd === null

  // Адрес держится в согласии с загруженным объёмом, чтобы возврат из просмотрщика не терял страницы
  useEffect(() => {
    if (!isLoading && items.length > 0 && items.length !== loadedOffset) {
      setSearchParams(writeOffset(searchParams, items.length), { replace: true })
    }
  }, [isLoading, items.length, loadedOffset, searchParams, setSearchParams])

  function handleFilterChange(rawValue: string): void {
    const nextStatus: GuidelineStatus | null = isGuidelineStatus(rawValue) ? rawValue : null
    setRestoreOffset(0)
    setSearchParams(writeStatus(searchParams, nextStatus))
  }

  function handleIcdSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (icdDraft.trim() !== '' && normalizeIcd(icdDraft) === null) {
      return
    }
    setRestoreOffset(0)
    setSearchParams(writeIcd(searchParams, icdDraft))
  }

  function handleIcdReset(): void {
    setIcdDraft('')
    setRestoreOffset(0)
    setSearchParams(writeIcd(searchParams, null))
  }

  function handleResetFilters(): void {
    setIcdDraft('')
    setRestoreOffset(0)
    // Оба фильтра снимаются одним переходом, иначе второй вызов перезапишет первый
    setSearchParams(writeIcd(writeStatus(searchParams, null), null))
  }

  function handleRequestDelete(guidelineId: string): void {
    setDeleteState((current) => requestDelete(current, guidelineId))
  }

  function handleCancelDelete(): void {
    setDeleteState((current) => cancelDelete(current))
  }

  async function handleConfirmDelete(guidelineId: string): Promise<void> {
    const deletedTitle = items.find((item) => item.guideline_id === guidelineId)?.title ?? null
    setDeleteState((current) => startDelete(current))
    try {
      await deleteGuideline(guidelineId)
      setHiddenIds((current) => hideGuideline(current, guidelineId))
      setDeleteState(IDLE_DELETE)
      notify({
        title: 'Клинрек удалён',
        description: deletedTitle ?? undefined,
      })
    } catch (caught) {
      setDeleteState(IDLE_DELETE)
      notify({
        title: 'Не удалось удалить клинрек',
        description: describeError(caught),
        tone: 'error',
      })
    }
  }

  const draftInvalid = icdDraft.trim() !== '' && normalizeIcd(icdDraft) === null

  function renderContent() {
    const view = selectListView({
      isLoading,
      error,
      count: visibleItems.length,
      status,
      icd,
    })

    if (view.kind === 'loading') {
      return <SkeletonRows />
    }

    if (view.kind === 'error') {
      return (
        <StateBox
          kind="error"
          title="Не удалось получить список клинреков"
          description={view.message}
          action={
            <Button variant="primary" onClick={reload}>
              Повторить
            </Button>
          }
        />
      )
    }

    if (view.kind === 'empty') {
      if (isEmptyLibrary) {
        return (
          <div className="flex flex-col gap-3">
            <p className="text-body text-text-muted">
              Библиотека пуста. Загрузите PDF клинических рекомендаций, чтобы начать проверку
              протоколов.
            </p>
            <UploadForm onUploaded={reload} />
          </div>
        )
      }
      return (
        <StateBox
          kind="empty"
          title="Под фильтр не подходит ни один клинрек"
          description="Измените фильтр по статусу или коду МКБ либо сбросьте его, чтобы увидеть всю библиотеку."
          action={<Button onClick={handleResetFilters}>Сбросить фильтры</Button>}
        />
      )
    }

    return (
      <>
        <ul>
          {visibleItems.map((guideline, position) => (
            <GuidelineRow
              key={guideline.guideline_id}
              guideline={guideline}
              index={position + 1}
              onRequestDelete={handleRequestDelete}
              onConfirmDelete={(guidelineId) => void handleConfirmDelete(guidelineId)}
              onCancelDelete={handleCancelDelete}
              deletePhase={deletePhaseFor(deleteState, guideline.guideline_id)}
            />
          ))}
        </ul>
        {hasMore ? (
          <div className="flex justify-center pt-2">
            <Button onClick={loadMore} disabled={isLoadingMore}>
              {isLoadingMore ? 'Загружаем…' : 'Показать ещё'}
            </Button>
          </div>
        ) : null}
      </>
    )
  }

  return (
    <section className="mx-auto flex w-full max-w-[1180px] flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <Overline>Библиотека</Overline>
          <h1>Клинические рекомендации</h1>
        </div>
        {isEmptyLibrary ? null : (
          <Button variant="primary" onClick={() => setIsUploadOpen(true)}>
            Загрузить PDF
          </Button>
        )}
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3 border-y border-border py-3">
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Фильтр по статусу">
          <Button
            variant={status === null ? 'primary' : 'ghost'}
            size="sm"
            aria-pressed={status === null}
            onClick={() => handleFilterChange('')}
          >
            Все статусы
          </Button>
          {GUIDELINE_STATUSES.map((value) => (
            <Button
              key={value}
              variant={status === value ? 'primary' : 'ghost'}
              size="sm"
              aria-pressed={status === value}
              onClick={() => handleFilterChange(value)}
            >
              {GUIDELINE_STATUS_LABELS[value]}
            </Button>
          ))}
        </div>

        <form className="flex items-center gap-2" onSubmit={handleIcdSubmit}>
          <label htmlFor="library-icd" className="text-caption text-text-muted">
            Код МКБ
          </label>
          <input
            id="library-icd"
            type="text"
            value={icdDraft}
            placeholder="I10"
            aria-invalid={draftInvalid}
            onChange={(event) => setIcdDraft(event.target.value)}
            className={cn(controlClassName, 'w-24')}
          />
          <Button type="submit" size="sm" disabled={draftInvalid}>
            Найти
          </Button>
          {icd === null ? null : (
            <Button variant="ghost" size="sm" onClick={handleIcdReset}>
              Сбросить
            </Button>
          )}
        </form>
      </div>

      {draftInvalid ? (
        <p className="text-caption text-danger" role="alert">
          {ICD_FORMAT_HINT}
        </p>
      ) : null}

      {visibleItems.length === 0 ? null : (
        <p className="text-caption text-text-muted">
          Клинреков: <Mono>{visibleItems.length}</Mono>
          {hasMore ? ' и ещё' : ''}
        </p>
      )}

      {renderContent()}

      <Dialog
        open={isUploadOpen}
        onOpenChange={setIsUploadOpen}
        title="Загрузка клинрека"
        description="PDF клинических рекомендаций, по которым будет проверяться протокол."
      >
        <UploadForm
          framed={false}
          onUploaded={() => {
            setIsUploadOpen(false)
            reload()
          }}
        />
      </Dialog>
    </section>
  )
}
