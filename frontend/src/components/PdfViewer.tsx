import type { PageViewport, PDFDocumentProxy, RenderTask } from 'pdfjs-dist'
import { type Ref, useEffect, useImperativeHandle, useRef, useState } from 'react'

import { type BBox, bboxToRect } from '../lib/bbox'
import { MAX_SCALE, MIN_SCALE, zoomIn, zoomOut } from '../lib/zoom'
import styles from './PdfViewer.module.css'

export type PdfViewerHandle = {
  /**
   * Перейти к странице и, если задана, подсветить область.
   *
   * Точка входа для будущих ссылок на чанки клинрека: пока её не вызывает никто, кроме тестов
   * и отладки, но контракт уже зафиксирован.
   */
  goTo: (target: { page: number; bbox?: BBox }) => void
}

export type PdfViewerProps = {
  pdf: PDFDocumentProxy
  page: number
  numPages: number
  scale: number
  onPageChange: (page: number) => void
  onScaleChange: (scale: number) => void
  ref?: Ref<PdfViewerHandle>
}

/**
 * Постраничный просмотр PDF.
 *
 * Компонент презентационный: документ, страница и масштаб приходят снаружи, поэтому масштаб
 * не сбрасывается при переходе между страницами.
 */
export function PdfViewer({
  pdf,
  page,
  numPages,
  scale,
  onPageChange,
  onScaleChange,
  ref,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [viewport, setViewport] = useState<PageViewport | null>(null)
  const [highlight, setHighlight] = useState<BBox | null>(null)

  useImperativeHandle(
    ref,
    () => ({
      goTo: (target) => {
        setHighlight(target.bbox ?? null)
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

  const highlightRect =
    viewport === null || highlight === null ? null : bboxToRect(highlight, viewport)

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
          {highlightRect === null ? null : (
            <span
              className={styles.highlight}
              style={{
                left: highlightRect.left,
                top: highlightRect.top,
                width: highlightRect.width,
                height: highlightRect.height,
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
