import type { PageViewport, PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import { type Ref, useEffect, useImperativeHandle, useRef, useState } from 'react'

import { type BBox, bboxesToRects } from '../lib/bbox'
import { MAX_SCALE, MIN_SCALE, zoomIn, zoomOut } from '../lib/zoom'
import styles from './PdfViewer.module.css'

export type PdfViewerHandle = {
  /**
   * Перейти к странице и, если задано, подсветить области.
   *
   * Точка входа для ссылок на фрагменты клинрека: чанк режется по смыслу и может
   * занимать несколько страниц, поэтому областей может быть несколько.
   */
  goTo: (target: { page: number; bbox?: BBox; rects?: readonly BBox[] }) => void
}

export type PdfViewerProps = {
  pdf: PDFDocumentProxy
  page: number
  numPages: number
  scale: number
  onPageChange: (page: number) => void
  onScaleChange: (scale: number) => void
  /** Прямоугольники подсветки на текущей странице, в координатах страницы PDF. */
  highlight?: readonly BBox[]
  ref?: Ref<PdfViewerHandle>
}

/**
 * Постраничный просмотр PDF.
 *
 * Компонент презентационный: документ, страница, масштаб и подсветка приходят снаружи,
 * поэтому масштаб не сбрасывается при переходе между страницами.
 */
export function PdfViewer({
  pdf,
  page,
  numPages,
  scale,
  onPageChange,
  onScaleChange,
  highlight = [],
  ref,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [viewport, setViewport] = useState<PageViewport | null>(null)
  const [manualHighlight, setManualHighlight] = useState<readonly BBox[]>([])

  // Подсветка из адреса страницы важнее программной: адрес — источник истины
  const activeHighlight = highlight.length > 0 ? highlight : manualHighlight

  useImperativeHandle(
    ref,
    () => ({
      goTo: (target) => {
        setManualHighlight(target.rects ?? (target.bbox === undefined ? [] : [target.bbox]))
        if (target.page !== page) {
          onPageChange(target.page)
        }
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

      const nextViewport = pdfPage.getViewport({ scale })
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
  }, [pdf, page, scale])

  const highlightRects = viewport === null ? [] : bboxesToRects(activeHighlight, viewport)

  return (
    <div className={styles.viewer}>
      <div className={styles.toolbar}>
        <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          Назад
        </button>
        <span className={styles.counter}>
          Страница {page} из {numPages}
        </span>
        <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= numPages}>
          Вперёд
        </button>

        <span className={styles.zoom}>
          <button
            type="button"
            onClick={() => onScaleChange(zoomOut(scale))}
            disabled={scale <= MIN_SCALE}
            aria-label="Уменьшить масштаб"
          >
            −
          </button>
          <span className={styles.zoomValue}>{Math.round(scale * 100)} %</span>
          <button
            type="button"
            onClick={() => onScaleChange(zoomIn(scale))}
            disabled={scale >= MAX_SCALE}
            aria-label="Увеличить масштаб"
          >
            +
          </button>
        </span>
      </div>

      <div className={styles.canvasArea}>
        <div className={styles.page}>
          <canvas ref={canvasRef} className={styles.canvas} />
          {highlightRects.map((rect, index) => (
            <span
              key={`${rect.left}-${rect.top}-${index}`}
              className={styles.highlight}
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
