import * as ToastPrimitive from '@radix-ui/react-toast'
import { X } from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { cn } from './cn'

export type ToastTone = 'success' | 'error'

export type ToastInput = {
  title: string
  description?: string
  tone?: ToastTone
}

type ToastMessage = ToastInput & { id: string; tone: ToastTone }

type Notify = (toast: ToastInput) => void

const ToastContext = createContext<Notify | null>(null)

/** Длительность показа: достаточно, чтобы прочитать две строки, и не мешает работе. */
const TOAST_DURATION = 5000

/**
 * Уведомления о результате действия.
 *
 * Уведомление не блокирует работу, объявляется как статусное сообщение и исчезает само.
 * Отдельного уведомления об успешной загрузке не нужно: результат виден в списке.
 *
 * Удаление по таймеру держит провайдер, а не Radix: так уведомление исчезает независимо от того,
 * успела ли проиграться анимация закрытия.
 */
export function ToastProvider({
  children,
  duration = TOAST_DURATION,
}: {
  children: ReactNode
  /** Время показа; в тестах задаётся короче, чтобы не ждать вживую. */
  duration?: number
}) {
  const [toasts, setToasts] = useState<readonly ToastMessage[]>([])
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: string) => {
    const timer = timers.current.get(id)
    if (timer !== undefined) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const notify = useCallback<Notify>(
    (toast) => {
      const id = crypto.randomUUID()
      setToasts((current) => [
        ...current,
        { ...toast, tone: toast.tone ?? 'success', id },
      ])
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), duration),
      )
    },
    [dismiss, duration],
  )

  // Уход со страницы не должен оставлять висящие таймеры
  useEffect(() => {
    const scheduled = timers.current
    return () => {
      for (const timer of scheduled.values()) {
        clearTimeout(timer)
      }
      scheduled.clear()
    }
  }, [])

  const contextValue = useMemo(() => notify, [notify])

  return (
    <ToastContext.Provider value={contextValue}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {toasts.map((toast) => (
          <ToastPrimitive.Root
            key={toast.id}
            role="status"
            aria-live="polite"
            duration={duration}
            onOpenChange={(open) => {
              if (!open) {
                dismiss(toast.id)
              }
            }}
            className={cn(
              'flex items-start gap-3 rounded-card border bg-surface px-3 py-2 shadow-panel',
              toast.tone === 'error' ? 'border-danger' : 'border-border',
            )}
          >
            <div className="flex min-w-0 flex-col gap-0.5">
              <ToastPrimitive.Title className="text-body font-medium text-text">
                {toast.title}
              </ToastPrimitive.Title>
              {toast.description === undefined ? null : (
                <ToastPrimitive.Description className="text-caption text-text-muted">
                  {toast.description}
                </ToastPrimitive.Description>
              )}
            </div>
            <ToastPrimitive.Close
              aria-label="Закрыть уведомление"
              className="ml-auto cursor-pointer rounded-chip p-1 text-text-muted hover:bg-surface-sunken hover:text-text"
            >
              <X aria-hidden="true" size={14} />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed right-4 bottom-4 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

/** Доступ к уведомлениям: вызывается из обработчиков действий, а не из презентационных компонентов. */
export function useToast(): Notify {
  const notify = useContext(ToastContext)
  if (notify === null) {
    throw new Error('useToast must be used inside ToastProvider')
  }
  return notify
}
