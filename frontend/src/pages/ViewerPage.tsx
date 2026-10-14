import { useEffect, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { type Guideline, getGuideline, guidelineFileUrl } from '../api/guidelines'
import { PdfViewer } from '../components/PdfViewer'
import { StateBox } from '../components/StateBox'
import { usePdfDocument } from '../hooks/usePdfDocument'
import { DEFAULT_SCALE } from '../lib/zoom'
import { PAGE_PARAM, readBackTarget, readPage } from '../store/urlParams'
import styles from './ViewerPage.module.css'

/** Метаданные клинрека вместе с идентификатором, к которому они относятся. */
type MetadataState = {
  guidelineId: string
  guideline: Guideline | null
  error: string | null
}

/**
 * Экран просмотра оригинала клинрека.
 *
 * Оригинал читается постранично через PDF.js; номер страницы живёт в адресе, поэтому на страницу
 * можно ссылаться. Масштаб держится в состоянии экрана и не сбрасывается при переходе между
 * страницами.
 */
export function ViewerPage() {
  const { guidelineId } = useParams<{ guidelineId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const backTo = readBackTarget(useLocation().state)

  const [scale, setScale] = useState(DEFAULT_SCALE)
  const [metadata, setMetadata] = useState<MetadataState | null>(null)

  const fileUrl = guidelineId === undefined ? null : guidelineFileUrl(guidelineId)
  const { pdf, numPages, isLoading, error } = usePdfDocument(fileUrl)

  useEffect(() => {
    if (guidelineId === undefined) {
      return
    }
    const controller = new AbortController()

    getGuideline(guidelineId, { signal: controller.signal }).then(
      (loaded) => {
        setMetadata({ guidelineId, guideline: loaded, error: null })
      },
      (caught: unknown) => {
        if (!controller.signal.aborted) {
          setMetadata({ guidelineId, guideline: null, error: describeError(caught) })
        }
      },
    )

    return () => controller.abort()
  }, [guidelineId])

  // Метаданные помечены идентификатором: чужой ответ не показывается на этом клинреке
  const currentMetadata =
    metadata !== null && guidelineId !== undefined && metadata.guidelineId === guidelineId
      ? metadata
      : null
  const guideline = currentMetadata?.guideline ?? null
  const metadataError = currentMetadata?.error ?? null

  // Номер из адреса может указывать за пределы документа: показываем доступную страницу
  const requestedPage = readPage(searchParams)
  const page = numPages > 0 ? Math.min(requestedPage, numPages) : requestedPage

  function handlePageChange(next: number): void {
    const params = new URLSearchParams(searchParams)
    if (next <= 1) {
      params.delete(PAGE_PARAM)
    } else {
      params.set(PAGE_PARAM, String(next))
    }
    setSearchParams(params, { replace: true })
  }

  function renderBody() {
    if (isLoading) {
      return <StateBox kind="loading" title="Загружаем документ…" />
    }
    if (error !== null || pdf === null) {
      return (
        <StateBox
          kind="error"
          title="Документ недоступен"
          description={error ?? 'PDF не загружен'}
        />
      )
    }
    return (
      <PdfViewer
        pdf={pdf}
        page={page}
        numPages={numPages}
        scale={scale}
        onPageChange={handlePageChange}
        onScaleChange={setScale}
      />
    )
  }

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <div className={styles.about}>
          <h1 className={styles.title}>{guideline?.title ?? 'Клинрек'}</h1>
          {guideline === null ? null : (
            <p className={styles.meta}>
              {guideline.filename} · версия {guideline.version}
            </p>
          )}
          {metadataError === null ? null : (
            <p className={styles.metaNote}>Не удалось получить метаданные: {metadataError}</p>
          )}
        </div>
        <Link className={styles.back} to={backTo}>
          ← В библиотеку
        </Link>
      </header>

      {renderBody()}
    </section>
  )
}
