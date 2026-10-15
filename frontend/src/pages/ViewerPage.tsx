import { useEffect, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { type Chunk, type Guideline, getChunk, getGuideline, guidelineFileUrl } from '../api/guidelines'
import { PdfViewer } from '../components/PdfViewer'
import { StateBox } from '../components/StateBox'
import { usePdfDocument } from '../hooks/usePdfDocument'
import type { BBox } from '../lib/bbox'
import { DEFAULT_SCALE } from '../lib/zoom'
import { PAGE_PARAM, readBackTarget, readChunkId, readPage } from '../store/urlParams'
import styles from './ViewerPage.module.css'

/** Метаданные клинрека вместе с идентификатором, к которому они относятся. */
type MetadataState = {
  guidelineId: string
  guideline: Guideline | null
  error: string | null
}

/** Загруженный фрагмент клинрека вместе с идентификатором, к которому он относится. */
type ChunkState = {
  chunkId: string
  chunk: Chunk | null
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
  const [chunk, setChunk] = useState<ChunkState | null>(null)

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

  const chunkId = readChunkId(searchParams)

  useEffect(() => {
    if (chunkId === null) {
      setChunk(null)
      return
    }
    const controller = new AbortController()

    getChunk(chunkId, { signal: controller.signal }).then(
      (loaded) => {
        setChunk({ chunkId, chunk: loaded, error: null })
      },
      (caught: unknown) => {
        if (!controller.signal.aborted) {
          setChunk({ chunkId, chunk: null, error: describeError(caught) })
        }
      },
    )

    return () => controller.abort()
  }, [chunkId])

  // Фрагмент помечен идентификатором: чужой ответ не подсвечивается на этом документе
  const currentChunk = chunk !== null && chunk.chunkId === chunkId ? chunk : null
  const activeChunk = currentChunk?.chunk ?? null
  const chunkError = currentChunk?.error ?? null

  // Номер из адреса может указывать за пределы документа: показываем доступную страницу
  const requestedPage = readPage(searchParams)
  const page = numPages > 0 ? Math.min(requestedPage, numPages) : requestedPage

  // На текущей странице подсвечиваются только её прямоугольники: остальные ждут перехода
  const highlight: BBox[] = (activeChunk?.rects ?? [])
    .filter((rect) => rect.page === page)
    .map((rect) => rect.bbox as BBox)

  // Страница фрагмента открывается сама, если в адресе не указана явно
  useEffect(() => {
    if (activeChunk === null || searchParams.get(PAGE_PARAM) !== null) {
      return
    }
    const params = new URLSearchParams(searchParams)
    if (activeChunk.page <= 1) {
      params.delete(PAGE_PARAM)
    } else {
      params.set(PAGE_PARAM, String(activeChunk.page))
    }
    setSearchParams(params, { replace: true })
  }, [activeChunk, searchParams, setSearchParams])

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
        highlight={highlight}
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
          {activeChunk === null ? null : (
            <>
              <p className={styles.metaNote}>
                Цитата{activeChunk.section === null ? '' : `: ${activeChunk.section}`}
              </p>
              <blockquote className={styles.meta}>{activeChunk.text}</blockquote>
            </>
          )}
          {chunkError === null ? null : (
            <p className={styles.metaNote}>Не удалось получить фрагмент: {chunkError}</p>
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
