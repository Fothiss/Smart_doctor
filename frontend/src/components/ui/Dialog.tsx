import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { type ReactNode, useEffect, useRef } from 'react'

/**
 * Модальное подтверждение или панель.
 *
 * Radix держит фокус внутри диалога, закрывает по Esc, блокирует прокрутку фона и возвращает
 * фокус на элемент, который был активен до открытия — при условии, что открытие идёт от действия
 * пользователя, как во всех экранах приложения.
 */
export type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children?: ReactNode
}

export function Dialog({ open, onOpenChange, title, description, children }: DialogProps) {
  // Возврат фокуса держим сами: на этом строится работа с клавиатуры, и полагаться на поведение
  // библиотеки в этом месте нельзя
  const openerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (open) {
      openerRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
      return
    }
    const opener = openerRef.current
    if (opener === null) {
      return
    }
    openerRef.current = null
    // Диалог убирается из DOM в этом же тике: фокус возвращаем после удаления оверлея
    const timer = setTimeout(() => opener.focus(), 0)
    return () => clearTimeout(timer)
  }, [open])

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-[rgb(23_24_26/35%)]" />
        <DialogPrimitive.Content className="fixed top-1/2 left-1/2 z-50 w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-surface p-5 shadow-panel">
          <DialogPrimitive.Title className="pr-8 text-h3 font-semibold text-ink">
            {title}
          </DialogPrimitive.Title>
          {description === undefined ? null : (
            <DialogPrimitive.Description className="mt-1 text-caption text-text-muted">
              {description}
            </DialogPrimitive.Description>
          )}
          <div className="mt-4">{children}</div>
          <DialogPrimitive.Close
            aria-label="Закрыть"
            className="absolute top-3 right-3 cursor-pointer rounded-chip p-1 text-text-muted hover:bg-surface-sunken hover:text-text"
          >
            <X aria-hidden="true" size={16} />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
