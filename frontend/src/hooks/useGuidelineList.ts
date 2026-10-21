import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '../api/client'
import {
  DEFAULT_PAGE_SIZE,
  type Guideline,
  type GuidelineStatus,
  listGuidelines,
} from '../api/guidelines'
import { collectPages, loadNextPage } from '../store/collectPages'
import { type GuidelineListState, initialListState } from '../store/guidelineList'

export type UseGuidelineListResult = {
  items: Guideline[]
  /** Идёт первичная загрузка или перезагрузка после смены фильтра. */
  isLoading: boolean
  /** Идёт догрузка следующей страницы. */
  isLoadingMore: boolean
  hasMore: boolean
  error: string | null
  loadMore: () => void
  reload: () => void
}

/**
 * Загрузка списка клинреков страницами.
 *
 * `initialOffset` приходит из адреса: при возврате из просмотрщика список восстанавливается до
 * той же позиции, а не с начала. Порядок запросов и слияние страниц живут в `store/collectPages`
 * и покрыты тестами отдельно от React.
 */
export function useGuidelineList(
  status: GuidelineStatus | null,
  icd: string | null = null,
  initialOffset = 0,
  pageSize = DEFAULT_PAGE_SIZE,
): UseGuidelineListResult {
  const [state, setState] = useState<GuidelineListState>(() => initialListState(status, icd))
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)
  const ticket = useRef(0)

  useEffect(() => {
    const currentTicket = ++ticket.current
    const controller = new AbortController()

    void (async () => {
      setIsLoading(true)
      setError(null)
      try {
        const collected = await collectPages(
          listGuidelines,
          status,
          icd,
          initialOffset,
          pageSize,
          { signal: controller.signal },
        )
        if (currentTicket === ticket.current) {
          setState(collected)
        }
      } catch (caught) {
        if (controller.signal.aborted || currentTicket !== ticket.current) {
          return
        }
        setError(describeError(caught))
      } finally {
        if (currentTicket === ticket.current) {
          setIsLoading(false)
        }
      }
    })()

    return () => controller.abort()
  }, [status, icd, initialOffset, pageSize, reloadToken])

  const loadMore = useCallback(() => {
    if (isLoading || isLoadingMore || !state.hasMore) {
      return
    }
    const currentTicket = ticket.current

    setIsLoadingMore(true)
    setError(null)

    void (async () => {
      try {
        const next = await loadNextPage(listGuidelines, state, pageSize)
        if (currentTicket === ticket.current) {
          setState(next)
        }
      } catch (caught) {
        if (currentTicket === ticket.current) {
          setError(describeError(caught))
        }
      } finally {
        if (currentTicket === ticket.current) {
          setIsLoadingMore(false)
        }
      }
    })()
  }, [isLoading, isLoadingMore, pageSize, state])

  const reload = useCallback(() => {
    setReloadToken((token) => token + 1)
  }, [])

  return {
    items: state.items,
    isLoading,
    isLoadingMore,
    hasMore: state.hasMore,
    error,
    loadMore,
    reload,
  }
}
