import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { uploadGuideline } from '../api/guidelines'
import { formatProgress, formatSize } from '../lib/format'
import { type UploadProblem, describeUploadError } from '../store/uploadErrors'
import styles from './UploadForm.module.css'

/**
 * Загрузка PDF клинрека.
 *
 * Файл выбирается и показывается до подтверждения — отправка начинается только по кнопке.
 * На время передачи повторный запуск недоступен. При отказе выбранный файл остаётся на месте,
 * чтобы его можно было заменить, не выбирая заново.
 */
export function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [progress, setProgress] = useState<number | null>(null)
  const [problem, setProblem] = useState<UploadProblem | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const isUploading = progress !== null

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
    if (file === null || isUploading) {
      return
    }
    setProblem(null)
    setProgress(0)

    try {
      await uploadGuideline({ file, title, onProgress: setProgress })
      setFile(null)
      setTitle('')
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

      <div className={styles.actions}>
        <button type="button" onClick={() => void submit()} disabled={file === null || isUploading}>
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
