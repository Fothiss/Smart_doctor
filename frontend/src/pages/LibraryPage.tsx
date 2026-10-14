import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  GUIDELINE_STATUSES,
  GUIDELINE_STATUS_LABELS,
  type GuidelineStatus,
  isGuidelineStatus,
} from '../api/guidelines'
import { GuidelineRow } from '../components/GuidelineRow'
import { StateBox } from '../components/StateBox'
import { UploadForm } from '../components/UploadForm'
import { useGuidelineList } from '../hooks/useGuidelineList'
import { selectListView } from '../store/listView'
import { readOffset, readStatus, writeOffset, writeStatus } from '../store/urlParams'
import styles from './LibraryPage.module.css'

/**
 * Экран библиотеки клинреков.
 *
 * Фильтр и позиция списка живут в адресе: возврат из просмотрщика восстанавливает список,
 * а ссылкой на отфильтрованную библиотеку можно поделиться.
 */
export function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = readStatus(searchParams)

  // Позиция для восстановления фиксируется на входе в экран: дальше догрузка идёт в состоянии хука
  const [restoreOffset, setRestoreOffset] = useState(() => readOffset(searchParams))

  const { items, isLoading, isLoadingMore, hasMore, error, loadMore, reload } = useGuidelineList(
    status,
    restoreOffset,
  )

  const loadedOffset = readOffset(searchParams)

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

  function renderContent() {
    const view = selectListView({ isLoading, error, count: items.length, status })

    if (view.kind === 'loading') {
      return <StateBox kind="loading" title="Загружаем библиотеку…" />
    }

    if (view.kind === 'error') {
      return (
        <StateBox
          kind="error"
          title="Не удалось получить список клинреков"
          description={view.message}
          action={
            <button type="button" onClick={reload}>
              Повторить
            </button>
          }
        />
      )
    }

    if (view.kind === 'empty') {
      return view.filtered ? (
        <StateBox
          kind="empty"
          title="С этим статусом клинреков нет"
          description="Измените фильтр или сбросьте его, чтобы увидеть всю библиотеку."
        />
      ) : (
        <StateBox
          kind="empty"
          title="Библиотека пуста"
          description="Загрузите PDF клинических рекомендаций, чтобы начать проверку протоколов."
        />
      )
    }

    return (
      <>
        <ul className={styles.list}>
          {items.map((guideline) => (
            <GuidelineRow key={guideline.guideline_id} guideline={guideline} />
          ))}
        </ul>
        {hasMore ? (
          <div className={styles.more}>
            <button type="button" onClick={loadMore} disabled={isLoadingMore}>
              {isLoadingMore ? 'Загружаем…' : 'Показать ещё'}
            </button>
          </div>
        ) : null}
      </>
    )
  }

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <h1>Библиотека клинреков</h1>
        <label className={styles.filter}>
          <span>Статус</span>
          <select value={status ?? ''} onChange={(event) => handleFilterChange(event.target.value)}>
            <option value="">Все статусы</option>
            {GUIDELINE_STATUSES.map((value) => (
              <option key={value} value={value}>
                {GUIDELINE_STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </header>

      <UploadForm onUploaded={reload} />

      {renderContent()}
    </section>
  )
}
