import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'

import { describeError } from '../api/client'
import { type Chunk, type Guideline, getChunk, getGuideline, guidelineFileUrl } from '../api/guidelines'
import { PdfViewer, type PdfViewerHandle } from '../components/PdfViewer'
import { StateBox } from '../components/StateBox'
import { Mono, Overline } from '../components/ui/Typography'
import { usePdfDocument } from '../hooks/usePdfDocument'
import type { BBox } from '../lib/bbox'
import { isTextFieldTarget, resolveViewerKey } from '../lib/viewerKeys'
import { DEFAULT_SCALE, zoomIn, zoomOut } from '../lib/zoom'
import { PAGE_PARAM, readBackTarget, readChunkId, readPage } from '../store/urlParams'

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
 *
 * Цитата фрагмента стоит рядом с документом: на широком экране её видно одновременно с подсветкой,
 * на узком — она уходит под документ и не перекрывает его.
 */
export function ViewerPage() {
  const { guidelineId } = useParams<{ guidelineId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const backTo = readBackTarget(useLocation().state)

  const [scale, setScale] = useState(DEFAULT_SCALE)
  const [fitToWidth, setFitToWidth] = useState(false)
  const [metadata, setMetadata] = useState<MetadataState | null>(null)
  const [chunk, setChunk] = useState<ChunkState | null>(null)
  const viewerRef = useRef<PdfViewerHandle>(null)

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
    // Без фрагмента в адресе запрашивать нечего; показать старый не даст проверка chunkId ниже
    if (chunkId === null) {
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

  // Клавиатура: стрелки листают страницы, «+»/«−» меняют масштаб, Home возвращает к цитате.
  // Пока фокус в поле номера страницы, сокращения молчат — иначе стрелки не работали бы в поле.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      const action = resolveViewerKey(event.key, {
        inTextField: isTextFieldTarget(event.target),
        hasQuote: activeChunk !== null,
      })
      if (action === 'none') {
        return
      }
      event.preventDefault()
      if (action === 'next-page' && page < numPages) {
        handlePageChange(page + 1)
      } else if (action === 'prev-page' && page > 1) {
        handlePageChange(page - 1)
      } else if (action === 'zoom-in') {
        setFitToWidth(false)
        setScale((current) => zoomIn(current))
      } else if (action === 'zoom-out') {
        setFitToWidth(false)
        setScale((current) => zoomOut(current))
      } else if (action === 'back-to-quote') {
        viewerRef.current?.scrollToHighlight()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  })

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
        ref={viewerRef}
        pdf={pdf}
        page={page}
        numPages={numPages}
        scale={scale}
        onPageChange={handlePageChange}
        onScaleChange={(next) => {
          setScale(next)
          setFitToWidth(false)
        }}
        fitToWidth={fitToWidth}
        onFitToWidthChange={setFitToWidth}
        highlight={highlight}
        hasQuote={activeChunk !== null}
      />
    )
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <Overline>Клинрек</Overline>
          <h1 className="text-h2">{guideline?.title ?? 'Документ'}</h1>
          {guideline === null ? null : (
            <p className="text-caption text-text-muted">
              {guideline.filename} · версия {guideline.version}
            </p>
          )}
          {metadataError === null ? null : (
            <p className="text-caption text-danger">
              Не удалось получить метаданные: {metadataError}
            </p>
          )}
          {chunkError === null ? null : (
            <p className="text-caption text-danger">Не удалось получить фрагмент: {chunkError}</p>
          )}
        </div>
        <Link className="whitespace-nowrap" to={backTo}>
          ← В библиотеку
        </Link>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-h-0 flex-col">{renderBody()}</div>

        {activeChunk === null ? null : (
          <aside
            aria-label="Цитата источника"
            className="flex min-h-0 flex-col gap-2 overflow-auto rounded-card border border-border bg-surface p-4 lg:max-h-full"
          >
            <Overline>Цитата</Overline>
            {activeChunk.section === null ? null : (
              <p className="text-caption text-text-muted">{activeChunk.section}</p>
            )}
            <blockquote className="border-l-2 border-[var(--color-mark-border)] pl-3 text-text">
              {activeChunk.text}
            </blockquote>
            <p className="flex items-center gap-1 text-caption text-text-muted">
              Страница <Mono className="text-text">{activeChunk.page}</Mono>
            </p>
          </aside>
        )}
      </div>
    </section>
  )
}
