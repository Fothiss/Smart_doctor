import { useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'

import { uploadGuideline } from '../api/guidelines'
import { ICD_FORMAT_HINT, parseIcdInput } from '../lib/icd'
import { formatProgress, formatSize } from '../lib/format'
import { type UploadProblem, describeUploadError } from '../store/uploadErrors'
import { canSubmitUpload } from '../store/uploadReadiness'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { Field, controlClassName } from './ui/Field'
import { cn } from './ui/cn'

/**
 * Загрузка PDF клинрека.
 *
 * Файл выбирается и показывается до подтверждения — отправка начинается только по кнопке.
 * На время передачи повторный запуск недоступен. При отказе выбранный файл остаётся на месте,
 * чтобы его можно было заменить, не выбирая заново.
 *
 * Коды МКБ обязательны: без них клинрек не выбрать в форме протокола, а сервер откажет в
 * загрузке. Ввод проверяется до отправки — опечатка не должна доходить до сервера.
 */
export function UploadForm({
  onUploaded,
  framed = true,
}: {
  onUploaded: () => void
  /** В диалоге форма уже стоит на поверхности — рамка карточки была бы второй. */
  framed?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [icdInput, setIcdInput] = useState('')
  const [progress, setProgress] = useState<number | null>(null)
  const [problem, setProblem] = useState<UploadProblem | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const isUploading = progress !== null
  const parsedCodes = parseIcdInput(icdInput)
  const canSubmit = canSubmitUpload({
    hasFile: file !== null,
    isUploading,
    parsed: parsedCodes,
  })

  function selectFile(next: File | null): void {
    setFile(next)
    setProblem(null)
    setProgress(null)
  }

  function clearFileInput(): void {
    if (inputRef.current !== null) {
      inputRef.current.value = ''
    }
  }

  async function submit(): Promise<void> {
    if (!canSubmit || file === null) {
      return
    }
    setProblem(null)
    setProgress(0)

    try {
      await uploadGuideline({ file, title, icdCodes: parsedCodes.codes, onProgress: setProgress })
      setFile(null)
      setTitle('')
      setIcdInput('')
      setProgress(null)
      clearFileInput()
      onUploaded()
    } catch (error) {
      setProgress(null)
      setProblem(describeUploadError(error))
    }
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>): void {
    event.preventDefault()
    setIsDragging(false)
    if (isUploading) {
      return
    }
    selectFile(event.dataTransfer.files.item(0))
  }

  const body = (
    <>
      <h2 className="text-lead font-semibold text-ink">Загрузить клинрек</h2>

      {/* Область перетаскивания — сама подпись файла: клавиатурный путь остаётся через input.
          Drag&drop — улучшение для указателя, доступность обеспечивает вложенный input. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <label
        className={cn(
          'flex flex-col items-center gap-2 rounded-card border border-dashed px-4 py-6 text-center',
          isDragging
            ? 'border-accent bg-accent-soft'
            : 'border-border-strong bg-surface-sunken',
        )}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <span className="text-body text-ink">Перетащите PDF сюда или выберите файл</span>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          disabled={isUploading}
          aria-label="PDF клинрека"
          className="max-w-full text-caption text-text-muted file:mr-2 file:cursor-pointer file:rounded-chip file:border file:border-border-strong file:bg-surface file:px-2 file:py-1 file:text-caption"
          onChange={(event) => selectFile(event.target.files?.item(0) ?? null)}
        />
        {file === null ? null : (
          <span className="text-caption font-medium text-ink">
            Выбран: {file.name} · {formatSize(file.size)}
          </span>
        )}
      </label>

      <Field id="upload-title" label="Название (необязательно)">
        {(props) => (
          <input
            {...props}
            type="text"
            value={title}
            disabled={isUploading}
            placeholder="По умолчанию — имя файла без расширения"
            onChange={(event) => setTitle(event.target.value)}
            className={controlClassName}
          />
        )}
      </Field>

      <Field
        id="upload-icd"
        label="Коды МКБ-10"
        hint={`${ICD_FORMAT_HINT}. Несколько кодов — через запятую.`}
        error={
          parsedCodes.invalid.length > 0
            ? `Не разобраны как код МКБ: ${parsedCodes.invalid.join(', ')}`
            : null
        }
      >
        {(props) => (
          <input
            {...props}
            type="text"
            value={icdInput}
            disabled={isUploading}
            placeholder="I10, I15"
            onChange={(event) => setIcdInput(event.target.value)}
            className={controlClassName}
          />
        )}
      </Field>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => void submit()} disabled={!canSubmit}>
          {isUploading ? 'Загружаем…' : 'Загрузить'}
        </Button>
        {progress === null ? null : (
          <span className="text-caption text-text-muted" role="status">
            Передано {formatProgress(progress)}
          </span>
        )}
      </div>

      {problem === null ? null : <ProblemView problem={problem} />}
    </>
  )

  return framed ? (
    <Card className="flex flex-col gap-3 p-4">{body}</Card>
  ) : (
    <div className="flex flex-col gap-3">{body}</div>
  )
}

/** Сообщение об отказе загрузки; для дубликата — переход к уже загруженному клинреку. */
function ProblemView({ problem }: { problem: UploadProblem }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-1 rounded-card border border-danger bg-danger-bg px-3 py-2 text-caption text-danger"
    >
      <p>{problem.message}</p>
      {problem.kind === 'duplicate' && problem.guidelineId !== null ? (
        <Link to={`/library/${problem.guidelineId}/view`}>Открыть загруженный клинрек</Link>
      ) : null}
    </div>
  )
}
