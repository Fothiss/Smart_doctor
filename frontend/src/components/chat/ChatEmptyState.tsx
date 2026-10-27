import { Stethoscope } from 'lucide-react'

import { Button } from '../ui/Button'

export type ChatEmptyStateProps = {
  suggestions: readonly string[]
  onPick: (text: string) => void
}

/**
 * Пустая лента: что это за экран и с чего начать.
 *
 * Подсказки заполняют поле вопроса, но не отправляют его: врач видит формулировку целиком
 * и может её поправить под своего пациента.
 */
export function ChatEmptyState({ suggestions, onPick }: ChatEmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <span className="flex size-12 items-center justify-center rounded-pill bg-accent-soft text-accent">
        <Stethoscope aria-hidden="true" size={22} />
      </span>
      <h1 className="text-h2 font-semibold text-ink">Спросите клинические рекомендации</h1>
      <p className="max-w-prose text-caption text-text-muted">
        Ответ строится только по выбранным документам, каждый факт помечен ссылкой на фрагмент.
        Если ответа в документах нет, система так и скажет.
      </p>
      <ul className="mt-2 flex w-full max-w-xl flex-col gap-2">
        {suggestions.map((text) => (
          <li key={text}>
            <Button
              variant="secondary"
              className="w-full justify-start text-left whitespace-normal text-caption"
              onClick={() => onPick(text)}
            >
              {text}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
