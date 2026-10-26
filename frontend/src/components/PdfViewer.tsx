import type { PageViewport, PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import { type Ref, useEffect, useImperativeHandle, useRef, useState } from 'react'

import { type BBox, bboxesToRects } from '../lib/bbox'
import { MAX_SCALE, MIN_SCALE, fitScale, zoomIn, zoomOut } from '../lib/zoom'
import { Button } from './ui/Button'
import { controlClassName } from './ui/Field'
import { Mono } from './ui/Typography'
import { cn } from './ui/cn'

export type PdfViewerHandle = {
  /**
   * Перейти к странице и, если задано, подсветить области.
   *
   * Точка входа для ссылок на фрагменты клинрека: чанк режется по смыслу и может
   * занимать несколько страниц, поэтому областей может быть несколько.
   */
  goTo: (target: { page: number; bbox?: BBox; rects?: readonly BBox[] }) => void
  /** Прокрутить к подсветке: кнопка «к цитате» и клавиатурное сокращение. */
  scrollToHighlight: () => void
}

export type PdfViewerProps = {
  pdf: PDFDocumentProxy
  page: number
  numPages: number
  scale: number
  onPageChange: (page: number) => void
  onScaleChange: (scale: number) => void
  /** Страница подогнана под ширину области; масштаб в этом режиме считает просмотрщик. */
  fitToWidth?: boolean
  onFitToWidthChange?: (fit: boolean) => void
  /** Прямоугольники подсветки на текущей странице, в координатах страницы PDF. */
  highlight?: readonly BBox[]
  /** Есть ли фрагмент, к которому можно вернуться. */
  hasQuote?: boolean
  ref?: Ref<PdfViewerHandle>
}

/** Внутренние отступы области просмотра: ширина страницы считается без них. */
const AREA_PADDING = 32

/**
 * Постраничный просмотр PDF.
 *
 * Документ, страница и подсветка приходят снаружи, поэтому масштаб не сбрасывается при переходе
 * между страницами. Область просмотра сама занимает доступную высоту: ни одного магического
 * вычитания из высоты окна.
 */
export function PdfViewer({
  pdf,
  page,
  numPages,
  scale,
  onPageChange,
  onScaleChange,
  fitToWidth = false,
  onFitToWidthChange,
  highlight = [],
  hasQuote = false,
  ref,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const areaRef = useRef<HTMLDivElement>(null)
  const highlightRef = useRef<HTMLSpanElement>(null)
  const [viewport, setViewport] = useState<PageViewport | null>(null)
  const [manualHighlight, setManualHighlight] = useState<readonly BBox[]>([])
  const [baseWidth, setBaseWidth] = useState<number | null>(null)
  const [areaWidth, setAreaWidth] = useState(0)
  const [pageError, setPageError] = useState<string | null>(null)
  const pageInputRef = useRef<HTMLInputElement>(null)

  // Подсветка из адреса страницы важнее программной: адрес — источник истины
  const activeHighlight = highlight.length > 0 ? highlight : manualHighlight

  const effectiveScale =
    fitToWidth && baseWidth !== null && areaWidth > 0
      ? fitScale(areaWidth - AREA_PADDING, baseWidth)
      : scale

  // Ширина области нужна для подгонки: без неё режим «по ширине» не имеет смысла
  useEffect(() => {
    const area = areaRef.current
    if (area === null || typeof ResizeObserver === 'undefined') {
      return
    }
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width !== undefined) {
        setAreaWidth(width)
      }
    })
    observer.observe(area)
    return () => observer.disconnect()
  }, [])

  useImperativeHandle(
    ref,
    () => ({
      goTo: (target) => {
        setManualHighlight(target.rects ?? (target.bbox === undefined ? [] : [target.bbox]))
        if (target.page !== page) {
          onPageChange(target.page)
        }
      },
      scrollToHighlight: () => {
        highlightRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      },
    }),
    [onPageChange, page],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }

    let cancelled = false
    let task: RenderTask | null = null

    void (async () => {
      const pdfPage = await pdf.getPage(page)
      if (cancelled) {
        return
      }

      const nextViewport = pdfPage.getViewport({ scale: effectiveScale })
      const context = canvas.getContext('2d')
      if (context === null) {
        return
      }

      const outputScale = window.devicePixelRatio || 1
      canvas.width = Math.floor(nextViewport.width * outputScale)
      canvas.height = Math.floor(nextViewport.height * outputScale)
      canvas.style.width = `${Math.floor(nextViewport.width)}px`
      canvas.style.height = `${Math.floor(nextViewport.height)}px`
      setViewport(nextViewport)
      setBaseWidth((current) => {
        const next = pdfPage.getViewport({ scale: 1 }).width
        return current !== null && Math.abs(current - next) < 0.5 ? current : next
      })

      task = pdfPage.render({
        canvas,
        canvasContext: context,
        viewport: nextViewport,
        transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
      })

      try {
        await task.promise
      } catch {
        // Отменённая отрисовка — не ошибка: так реагируем на смену страницы или масштаба
      }
    })()

    return () => {
      cancelled = true
      task?.cancel()
    }
  }, [pdf, page, effectiveScale])

  const highlightRects = viewport === null ? [] : bboxesToRects(activeHighlight, viewport)

  /** Перейти на введённый номер: за границы документа не пускаем и объясняем предел. */
  function commitPage(): void {
    const parsed = Number(pageInputRef.current?.value.trim() ?? '')
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > numPages) {
      setPageError(`Страница — целое число от 1 до ${numPages}`)
      return
    }
    setPageError(null)
    onPageChange(parsed)
  }

  /** Переход кнопками сбрасывает подсказку о недопустимом номере. */
  function goToPage(next: number): void {
    setPageError(null)
    onPageChange(next)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface px-3 py-2">
        <div className="flex items-center gap-1">
          <Button size="sm" onClick={() => goToPage(page - 1)} disabled={page <= 1}>
            Назад
          </Button>
          <Button size="sm" onClick={() => goToPage(page + 1)} disabled={page >= numPages}>
            Вперёд
          </Button>
        </div>

        <span className="flex items-center gap-1 text-caption text-text-muted">
          Страница
          <input
            key={page}
            ref={pageInputRef}
            type="text"
            inputMode="numeric"
            aria-label="Номер страницы"
            aria-invalid={pageError !== null}
            defaultValue={String(page)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                commitPage()
              }
              if (event.key === 'Escape') {
                event.currentTarget.value = String(page)
                setPageError(null)
              }
            }}
            onBlur={commitPage}
            className={cn(controlClassName, 'w-14 py-1 text-center')}
          />
          из <Mono className="text-text">{numPages}</Mono>
        </span>

        <div className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            onClick={() => {
              onFitToWidthChange?.(false)
              onScaleChange(zoomOut(effectiveScale))
            }}
            disabled={effectiveScale <= MIN_SCALE}
            aria-label="Уменьшить масштаб"
          >
            −
          </Button>
          <Mono className="w-12 text-center text-text-muted">
            {Math.round(effectiveScale * 100)} %
          </Mono>
          <Button
            size="sm"
            onClick={() => {
              onFitToWidthChange?.(false)
              onScaleChange(zoomIn(effectiveScale))
            }}
            disabled={effectiveScale >= MAX_SCALE}
            aria-label="Увеличить масштаб"
          >
            +
          </Button>
          <Button
            size="sm"
            onClick={() => onFitToWidthChange?.(true)}
            aria-pressed={fitToWidth}
            className={fitToWidth ? 'border-accent text-accent' : undefined}
          >
            По ширине
          </Button>
          {hasQuote ? (
            <Button size="sm" variant="ghost" onClick={() => highlightRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })}>
              К цитате
            </Button>
          ) : null}
        </div>
      </div>

      {pageError === null ? null : (
        <p className="text-caption text-danger" role="alert">
          {pageError}
        </p>
      )}

      <div
        ref={areaRef}
        className="min-h-0 flex-1 overflow-auto rounded-card border border-border bg-surface-sunken p-4"
      >
        <div className="relative mx-auto w-fit shadow-card">
          <canvas ref={canvasRef} className="block bg-surface" />
          {highlightRects.map((rect, index) => (
            <span
              key={`${rect.left}-${rect.top}-${index}`}
              ref={index === 0 ? highlightRef : undefined}
              className="pointer-events-none absolute rounded-[2px] bg-[var(--color-mark)]/45 outline-2 outline-[var(--color-mark-border)]"
              style={{
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
