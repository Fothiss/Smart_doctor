/**
 * Сессия чата живёт в памяти приложения.
 *
 * Лента должна переживать переходы между разделами, но не перезагрузку страницы: после F5
 * разговор начинается заново. `sessionStorage` для этого не годится — он как раз переживает
 * перезагрузку. Поэтому состояние поднято выше маршрутов: экран чата размонтируется, а
 * провайдер остаётся.
 */

import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'

import type { ChatEntry } from './chat'

export type ChatSession = {
  entries: ChatEntry[]
  /** Черновик вопроса: переход в библиотеку не должен стирать набранное. */
  draft: string
  append: (entry: ChatEntry) => void
  setDraft: (value: string) => void
  reset: () => void
}

const ChatSessionContext = createContext<ChatSession | null>(null)

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<ChatEntry[]>([])
  const [draft, setDraft] = useState('')

  const append = useCallback((entry: ChatEntry) => {
    setEntries((current) => [...current, entry])
  }, [])

  const reset = useCallback(() => {
    setEntries([])
    setDraft('')
  }, [])

  const value = useMemo<ChatSession>(
    () => ({ entries, draft, append, setDraft, reset }),
    [entries, draft, append, reset],
  )

  return <ChatSessionContext.Provider value={value}>{children}</ChatSessionContext.Provider>
}

/** Доступ к сессии чата; вне провайдера — ошибка конфигурации, а не пустой чат. */
export function useChatSession(): ChatSession {
  const session = useContext(ChatSessionContext)
  if (session === null) {
    throw new Error('useChatSession must be used inside ChatSessionProvider')
  }
  return session
}
