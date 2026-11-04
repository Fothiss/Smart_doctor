import { Button } from '../ui/Button'
import { LogoMark } from '../ui/Logo'

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
    <div className="flex animate-rise flex-col items-center gap-3 py-12 text-center">
      <span className="flex size-14 items-center justify-center rounded-panel border border-border bg-surface text-accent shadow-card">
        <LogoMark size={26} />
      </span>
      <h1 className="text-h1">Спросите клинические рекомендации</h1>
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
