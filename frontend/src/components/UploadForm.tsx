import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { uploadGuideline } from '../api/guidelines'
import { ICD_FORMAT_HINT, parseIcdInput } from '../lib/icd'
import { formatProgress, formatSize } from '../lib/format'
import { type UploadProblem, describeUploadError } from '../store/uploadErrors'
import { canSubmitUpload } from '../store/uploadReadiness'
import styles from './UploadForm.module.css'

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
export function UploadForm({ onUploaded }: { onUploaded: () => void }) {
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

  function handleDrop(event: React.DragEvent<HTMLDivElement>): void {
    event.preventDefault()
    setIsDragging(false)
    if (isUploading) {
      return
    }
    selectFile(event.dataTransfer.files.item(0))
  }

  return (
    <section className={styles.form}>
      <h2 className={styles.heading}>Загрузить клинрек</h2>

      <div
        className={isDragging ? `${styles.dropzone} ${styles.dragging}` : styles.dropzone}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          disabled={isUploading}
          onChange={(event) => selectFile(event.target.files?.item(0) ?? null)}
        />
        <p className={styles.hint}>Перетащите PDF сюда или выберите файл</p>
        {file === null ? null : (
          <p className={styles.chosen}>
            Выбран: {file.name} · {formatSize(file.size)}
          </p>
        )}
      </div>

      <label className={styles.titleField}>
        <span>Название (необязательно)</span>
        <input
          type="text"
          value={title}
          disabled={isUploading}
          placeholder="По умолчанию — имя файла без расширения"
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>

      <label className={styles.titleField}>
        <span>Коды МКБ-10</span>
        <input
          type="text"
          value={icdInput}
          disabled={isUploading}
          placeholder="I10, I15"
          aria-invalid={parsedCodes.invalid.length > 0}
          onChange={(event) => setIcdInput(event.target.value)}
        />
      </label>
      {parsedCodes.invalid.length > 0 ? (
        <p className={styles.hint} role="alert">
          Не разобраны как код МКБ: {parsedCodes.invalid.join(', ')}. {ICD_FORMAT_HINT}
        </p>
      ) : (
        <p className={styles.hint}>{ICD_FORMAT_HINT}. Несколько кодов — через запятую.</p>
      )}

      <div className={styles.actions}>
        <button type="button" onClick={() => void submit()} disabled={!canSubmit}>
          {isUploading ? 'Загружаем…' : 'Загрузить'}
        </button>
        {progress === null ? null : (
          <span className={styles.progress} role="status">
            Передано {formatProgress(progress)}
          </span>
        )}
      </div>

      {problem === null ? null : <ProblemView problem={problem} />}
    </section>
  )
}

/** Сообщение об отказе загрузки; для дубликата — переход к уже загруженному клинреку. */
function ProblemView({ problem }: { problem: UploadProblem }) {
  return (
    <div className={styles.problem} role="alert">
      <p className={styles.problemText}>{problem.message}</p>
      {problem.kind === 'duplicate' && problem.guidelineId !== null ? (
        <Link to={`/library/${problem.guidelineId}/view`}>Открыть загруженный клинрек</Link>
      ) : null}
    </div>
  )
}
