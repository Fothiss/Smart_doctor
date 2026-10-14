import { GlobalWorkerOptions, type PDFDocumentProxy, getDocument } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { useEffect, useState } from 'react'

import { describePdfError } from '../store/pdfErrors'

/**
 * Worker PDF.js собирается Vite как отдельный ассет (`?url`), поэтому он попадает и в
 * development, и в собранный бандл. Путь через `public/` здесь не нужен.
 */
GlobalWorkerOptions.workerSrc = workerUrl

export type UsePdfDocumentResult = {
  pdf: PDFDocumentProxy | null
  numPages: number
  isLoading: boolean
  error: string | null
}

/** Результат загрузки вместе с адресом, к которому он относится. */
type LoadedState = {
  url: string | null
  pdf: PDFDocumentProxy | null
  numPages: number
  error: string | null
}

const IDLE_STATE: LoadedState = { url: null, pdf: null, numPages: 0, error: null }

/**
 * Загрузка оригинала клинрека в PDF.js.
 *
 * Документ берётся по адресу `/api/guidelines/{id}/file`: PDF.js сам ходит за частями файла,
 * опираясь на поддержку `Range` сервером, и не тянет весь PDF целиком.
 *
 * Результат помечен адресом, к которому относится: пока адрес не совпадает с запрошенным,
 * наружу отдаётся состояние загрузки. Так переход на другой документ не показывает старые
 * страницы и не требует синхронной установки состояния внутри эффекта.
 */
export function usePdfDocument(url: string | null): UsePdfDocumentResult {
  const [state, setState] = useState<LoadedState>(IDLE_STATE)

  useEffect(() => {
    if (url === null) {
      return
    }

    let cancelled = false
    const task = getDocument({ url })

    task.promise.then(
      (loaded) => {
        if (!cancelled) {
          setState({ url, pdf: loaded, numPages: loaded.numPages, error: null })
        }
      },
      (caught: unknown) => {
        if (!cancelled) {
          setState({ url, pdf: null, numPages: 0, error: describePdfError(caught) })
        }
      },
    )

    return () => {
      cancelled = true
      void task.destroy()
    }
  }, [url])

  if (url === null) {
    return { pdf: null, numPages: 0, isLoading: false, error: null }
  }

  const settled = state.url === url
  return {
    pdf: settled ? state.pdf : null,
    numPages: settled ? state.numPages : 0,
    isLoading: !settled,
    error: settled ? state.error : null,
  }
}
