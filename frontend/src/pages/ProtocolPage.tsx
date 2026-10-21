import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { describeError } from '../api/client'
import { type Guideline, listGuidelines } from '../api/guidelines'
import { type ProtocolDraftResponse, validateProtocol } from '../api/protocols'
import { StateBox } from '../components/StateBox'
import { ICD_FORMAT_HINT, sortByIcdMatch } from '../lib/icd'
import { describeValidationError } from '../store/protocolErrors'
import {
  type ProtocolFormDraft,
  addPrescription,
  canValidate,
  draftProblems,
  emptyProtocolForm,
  hasProblem,
  removePrescription,
  toDraftRequest,
  updatePrescription,
} from '../store/protocolForm'
import styles from './ProtocolPage.module.css'

type GuidelinesState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; items: Guideline[] }

type ValidationState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; response: ProtocolDraftResponse }

/**
 * Экран ввода врачебного протокола.
 *
 * Черновик живёт в состоянии экрана и никуда не сохраняется: сервер проверяет форму,
 * подтверждает выбранный клинрек и возвращает пункты, которые пойдут в проверку. Сама
 * проверка на соответствие клинреку появится следующим изменением, поэтому экран не
 * обещает вердикт.
 */
export function ProtocolPage() {
  const [form, setForm] = useState<ProtocolFormDraft>(emptyProtocolForm)
  const [guidelines, setGuidelines] = useState<GuidelinesState>({ kind: 'loading' })
  const [selectedId, setSelectedId] = useState('')
  const [validation, setValidation] = useState<ValidationState>({ kind: 'idle' })

  useEffect(() => {
    const controller = new AbortController()

    void (async () => {
      try {
        const items = await listGuidelines(
          { status: 'ready' },
          { signal: controller.signal },
        )
        if (!controller.signal.aborted) {
          setGuidelines({ kind: 'ready', items })
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setGuidelines({ kind: 'error', message: describeError(caught) })
        }
      }
    })()

    return () => controller.abort()
  }, [])

  const problems = draftProblems(form)
  const readyItems = guidelines.kind === 'ready' ? guidelines.items : []
  const orderedItems = sortByIcdMatch(readyItems, form.icdCode)
  const canSubmit = canValidate(form, selectedId === '' ? null : selectedId)

  function patchForm(changes: Partial<ProtocolFormDraft>): void {
    setForm((current) => ({ ...current, ...changes }))
    setValidation({ kind: 'idle' })
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (!canSubmit) {
      return
    }
    setValidation({ kind: 'loading' })
    try {
      const response = await validateProtocol(toDraftRequest(form, selectedId))
      setValidation({ kind: 'done', response })
    } catch (caught) {
      setValidation({ kind: 'error', message: describeValidationError(caught) })
    }
  }

  function renderGuidelineField() {
    if (guidelines.kind === 'loading') {
      return <p className={styles.hint}>Загружаем клинреки…</p>
    }
    if (guidelines.kind === 'error') {
      return (
        <div className={styles.hint} role="alert">
          Не удалось получить список клинреков: {guidelines.message}
        </div>
      )
    }
    if (guidelines.items.length === 0) {
      return (
        <StateBox
          kind="empty"
          title="Нет клинреков, готовых к проверке"
          description="Загрузите PDF клинических рекомендаций и дождитесь окончания обработки."
          action={
            <Link to="/library">
              <button type="button">Перейти в библиотеку</button>
            </Link>
          }
        />
      )
    }
    return (
      <select
        value={selectedId}
        onChange={(event) => setSelectedId(event.target.value)}
        aria-label="Клинрек"
      >
        <option value="">Выберите клинрек</option>
        {orderedItems.map((guideline) => (
          <option key={guideline.guideline_id} value={guideline.guideline_id}>
            {describeGuideline(guideline)}
          </option>
        ))}
      </select>
    )
  }

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <h1>Протокол</h1>
        <p className={styles.hint}>
          Заполните протокол и выберите клинрек — сервер проверит форму и покажет, какие
          пункты пойдут в проверку.
        </p>
      </header>

      <form className={styles.form} onSubmit={(event) => void submit(event)}>
        <label className={styles.field}>
          <span>Жалобы</span>
          <textarea
            rows={3}
            value={form.complaints}
            aria-invalid={hasProblem(problems, 'complaints')}
            onChange={(event) => patchForm({ complaints: event.target.value })}
          />
        </label>

        <div className={styles.row}>
          <label className={styles.field}>
            <span>Код МКБ-10</span>
            <input
              type="text"
              value={form.icdCode}
              placeholder="I10"
              aria-invalid={hasProblem(problems, 'diagnosis.code')}
              onChange={(event) => patchForm({ icdCode: event.target.value })}
            />
          </label>
          <label className={styles.field}>
            <span>Название диагноза</span>
            <input
              type="text"
              value={form.diagnosisName}
              aria-invalid={hasProblem(problems, 'diagnosis.name')}
              onChange={(event) => patchForm({ diagnosisName: event.target.value })}
            />
          </label>
        </div>
        <p className={styles.hint}>{ICD_FORMAT_HINT}</p>

        <label className={styles.field}>
          <span>Описание диагноза (необязательно)</span>
          <textarea
            rows={2}
            value={form.diagnosisDescription}
            onChange={(event) => patchForm({ diagnosisDescription: event.target.value })}
          />
        </label>

        <fieldset className={styles.prescriptions}>
          <legend>Назначения</legend>
          {form.prescriptions.length === 0 ? (
            <p className={styles.hint}>
              Назначений пока нет: добавьте препарат или процедуру.
            </p>
          ) : null}
          <ul className={styles.prescriptionList}>
            {form.prescriptions.map((item, index) => (
              <li key={index} className={styles.prescription}>
                <label className={styles.field}>
                  <span>Вид</span>
                  <select
                    value={item.kind}
                    onChange={(event) =>
                      updatePrescription(form, index, {
                        kind: event.target.value === 'procedure' ? 'procedure' : 'drug',
                      })
                    }
                  >
                    <option value="drug">Препарат</option>
                    <option value="procedure">Процедура</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Название</span>
                  <input
                    type="text"
                    value={item.name}
                    aria-invalid={hasProblem(problems, `prescriptions[${index}].name`)}
                    onChange={(event) =>
                      updatePrescription(form, index, { name: event.target.value })
                    }
                  />
                </label>
                {item.kind === 'drug' ? (
                  <>
                    <label className={styles.field}>
                      <span>Дозировка</span>
                      <input
                        type="text"
                        value={item.dose}
                        placeholder="5 мг"
                        onChange={(event) =>
                          updatePrescription(form, index, { dose: event.target.value })
                        }
                      />
                    </label>
                    <label className={styles.field}>
                      <span>Кратность</span>
                      <input
                        type="text"
                        value={item.frequency}
                        placeholder="1 раз в сутки"
                        onChange={(event) =>
                          updatePrescription(form, index, { frequency: event.target.value })
                        }
                      />
                    </label>
                    <label className={styles.field}>
                      <span>Длительность</span>
                      <input
                        type="text"
                        value={item.duration}
                        placeholder="постоянно"
                        onChange={(event) =>
                          updatePrescription(form, index, { duration: event.target.value })
                        }
                      />
                    </label>
                  </>
                ) : null}
                <button
                  type="button"
                  onClick={() => patchForm(removePrescription(form, index))}
                >
                  Удалить назначение
                </button>
              </li>
            ))}
          </ul>
          <div className={styles.prescriptionActions}>
            <button
              type="button"
              onClick={() => patchForm(addPrescription(form, 'drug'))}
            >
              Добавить препарат
            </button>
            <button
              type="button"
              onClick={() => patchForm(addPrescription(form, 'procedure'))}
            >
              Добавить процедуру
            </button>
          </div>
        </fieldset>

        <label className={styles.field}>
          <span>Клинрек для проверки</span>
          {renderGuidelineField()}
        </label>

        {problems.length > 0 ? (
          <ul className={styles.problems} role="alert">
            {problems.map((problem) => (
              <li key={problem.field}>{problem.message}</li>
            ))}
          </ul>
        ) : null}

        <div className={styles.actions}>
          <button type="submit" disabled={!canSubmit || validation.kind === 'loading'}>
            {validation.kind === 'loading' ? 'Проверяем форму…' : 'Проверить форму'}
          </button>
        </div>
      </form>

      {renderValidation()}
    </section>
  )

  function renderValidation() {
    if (validation.kind === 'idle' || validation.kind === 'loading') {
      return null
    }
    if (validation.kind === 'error') {
      return (
        <StateBox
          kind="error"
          title="Черновик не принят"
          description={validation.message}
        />
      )
    }
    const { guideline, statements } = validation.response
    const codes = guideline.icd_codes ?? []
    return (
      <section className={styles.result}>
        <h2>Черновик принят</h2>
        <p className={styles.hint}>
          Клинрек: {guideline.title} · версия {guideline.version} · коды МКБ:{' '}
          {codes.length === 0 ? 'не указаны' : codes.join(', ')}
        </p>
        <p className={styles.hint}>
          Пунктов к проверке: {statements.length}. Черновик не сохранён — он живёт только на
          этом экране.
        </p>
        <ol className={styles.statements}>
          {statements.map((statement) => (
            <li key={statement}>{statement}</li>
          ))}
        </ol>
      </section>
    )
  }
}

/** Подпись клинрека в списке выбора: название, версия и коды МКБ. */
function describeGuideline(guideline: Guideline): string {
  const codes = guideline.icd_codes ?? []
  const suffix = codes.length === 0 ? 'коды МКБ не указаны' : codes.join(', ')
  return `${guideline.title} · версия ${guideline.version} · ${suffix}`
}
