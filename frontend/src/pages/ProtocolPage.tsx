import { type FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { describeError } from '../api/client'
import { type Guideline, listGuidelines } from '../api/guidelines'
import { type ProtocolDraftResponse, validateProtocol } from '../api/protocols'
import { StateBox } from '../components/StateBox'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Combobox, type ComboboxItem } from '../components/ui/Combobox'
import { Field, controlClassName } from '../components/ui/Field'
import { Overline } from '../components/ui/Typography'
import { ICD_FORMAT_HINT, sortByIcdMatch } from '../lib/icd'
import { describeValidationError } from '../store/protocolErrors'
import {
  type ProtocolFormDraft,
  addPrescription,
  draftProblems,
  emptyProtocolForm,
  firstInvalidField,
  problemMessage,
  removePrescription,
  toDraftRequest,
  updatePrescription,
} from '../store/protocolForm'

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
 * подтверждает выбранный клинрек и возвращает пункты, которые пойдут в проверку.
 *
 * Экран в две колонки: слева поля, справа закреплённый выбор клинрека и кнопка отправки —
 * заполнять длинную форму и искать кнопку внизу не приходится. Ошибки стоят у своих полей,
 * а при отправке фокус уходит на первое невалидное.
 */
export function ProtocolPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<ProtocolFormDraft>(emptyProtocolForm)
  const [guidelines, setGuidelines] = useState<GuidelinesState>({ kind: 'loading' })
  const [selectedId, setSelectedId] = useState('')
  const [guidelineError, setGuidelineError] = useState<string | null>(null)
  const [validation, setValidation] = useState<ValidationState>({ kind: 'idle' })

  useEffect(() => {
    const controller = new AbortController()

    void (async () => {
      try {
        const items = await listGuidelines({ status: 'ready' }, { signal: controller.signal })
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
  const comboboxItems: ComboboxItem[] = orderedItems.map((guideline) => ({
    value: guideline.guideline_id,
    label: describeGuideline(guideline),
  }))
  const canSubmit = validation.kind !== 'loading'

  function patchForm(changes: Partial<ProtocolFormDraft>): void {
    setForm((current) => ({ ...current, ...changes }))
    setValidation({ kind: 'idle' })
  }

  /** Идентификатор поля формы: по нему переводим фокус на ошибку. */
  function fieldId(field: string): string {
    if (field === 'complaints') {
      return 'protocol-complaints'
    }
    if (field === 'diagnosis.code') {
      return 'protocol-icd'
    }
    if (field === 'diagnosis.name') {
      return 'protocol-diagnosis-name'
    }
    const prescription = /^prescriptions\[(\d+)\](?:\.name)?$/.exec(field)
    if (prescription !== null) {
      return `protocol-prescription-${prescription[1]}-name`
    }
    return 'protocol-complaints'
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const invalid = firstInvalidField(problems)
    if (invalid !== null) {
      // Отправка не выполняется, но врач сразу видит, какое поле мешает
      const element = document.getElementById(fieldId(invalid))
      element?.focus()
      element?.scrollIntoView({ block: 'center' })
      return
    }
    if (selectedId === '') {
      setGuidelineError('Выберите клинрек для проверки')
      document.getElementById('protocol-guideline')?.focus()
      return
    }
    setGuidelineError(null)
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
      return <p className="text-caption text-text-muted">Загружаем клинреки…</p>
    }
    if (guidelines.kind === 'error') {
      return (
        <p className="text-caption text-danger" role="alert">
          Не удалось получить список клинреков: {guidelines.message}
        </p>
      )
    }
    if (guidelines.items.length === 0) {
      return (
        <StateBox
          kind="empty"
          title="Нет клинреков, готовых к проверке"
          description="Загрузите PDF клинических рекомендаций и дождитесь окончания обработки."
          action={
            <Button onClick={() => void navigate('/library')}>Перейти в библиотеку</Button>
          }
        />
      )
    }
    return (
      <Combobox
        id="protocol-guideline"
        items={comboboxItems}
        value={selectedId === '' ? null : selectedId}
        onChange={(next) => {
          setSelectedId(next)
          setGuidelineError(null)
        }}
        label="Клинрек"
        placeholder="Выберите клинрек"
        searchPlaceholder="Поиск по названию или коду МКБ"
        aria-describedby={guidelineError === null ? undefined : 'protocol-guideline-error'}
      />
    )
  }

  function renderValidation() {
    if (validation.kind === 'idle' || validation.kind === 'loading') {
      return null
    }
    if (validation.kind === 'error') {
      return (
        <StateBox kind="error" title="Черновик не принят" description={validation.message} />
      )
    }
    const { guideline, statements } = validation.response
    const codes = guideline.icd_codes ?? []
    return (
      <Card className="flex flex-col gap-2 p-4">
        <h2 className="text-h3">Черновик принят</h2>
        <p className="text-caption text-text-muted">
          Клинрек: {guideline.title} · версия {guideline.version} · коды МКБ:{' '}
          {codes.length === 0 ? 'не указаны' : codes.join(', ')}
        </p>
        <p className="text-caption text-text-muted">
          Пунктов к проверке: {statements.length}. Черновик не сохранён — он живёт только на этом
          экране.
        </p>
        <ol className="flex flex-col gap-1 pl-5 text-body">
          {statements.map((statement) => (
            <li key={statement}>{statement}</li>
          ))}
        </ol>
      </Card>
    )
  }

  return (
    <section className="flex flex-col gap-5">
      <header className="flex flex-col gap-1">
        <Overline>Протокол</Overline>
        <h1>Новый протокол</h1>
        <p className="max-w-prose text-caption text-text-muted">
          Заполните протокол и выберите клинрек — сервер проверит форму и покажет, какие пункты
          пойдут в проверку.
        </p>
      </header>

      <form className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_19rem]" onSubmit={(event) => void submit(event)}>
        <div className="flex flex-col gap-4">
          <Field
            id="protocol-complaints"
            label="Жалобы"
            error={problemMessage(problems, 'complaints')}
          >
            {(props) => (
              <textarea
                {...props}
                rows={3}
                value={form.complaints}
                onChange={(event) => patchForm({ complaints: event.target.value })}
                className={controlClassName}
              />
            )}
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              id="protocol-icd"
              label="Код МКБ-10"
              hint={ICD_FORMAT_HINT}
              error={problemMessage(problems, 'diagnosis.code')}
            >
              {(props) => (
                <input
                  {...props}
                  type="text"
                  value={form.icdCode}
                  placeholder="I10"
                  onChange={(event) => patchForm({ icdCode: event.target.value })}
                  className={controlClassName}
                />
              )}
            </Field>

            <Field
              id="protocol-diagnosis-name"
              label="Название диагноза"
              error={problemMessage(problems, 'diagnosis.name')}
            >
              {(props) => (
                <input
                  {...props}
                  type="text"
                  value={form.diagnosisName}
                  onChange={(event) => patchForm({ diagnosisName: event.target.value })}
                  className={controlClassName}
                />
              )}
            </Field>
          </div>

          <Field
            id="protocol-description"
            label="Описание диагноза (необязательно)"
          >
            {(props) => (
              <textarea
                {...props}
                rows={2}
                value={form.diagnosisDescription}
                onChange={(event) => patchForm({ diagnosisDescription: event.target.value })}
                className={controlClassName}
              />
            )}
          </Field>

          <fieldset className="flex flex-col gap-3 rounded-card border border-border p-4">
            <legend className="px-1 text-caption text-text-muted">Назначения</legend>
            {form.prescriptions.length === 0 ? (
              <p className="text-caption text-text-muted">
                Назначений пока нет: добавьте препарат или процедуру.
              </p>
            ) : null}

            {form.prescriptions.map((item, index) => (
              <div
                key={index}
                className="flex flex-col gap-3 rounded-card border border-border bg-surface-sunken/40 p-3"
              >
                <div className="flex items-end gap-3">
                  <span className="font-mono text-caption text-text-faint">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <Field id={`protocol-prescription-${index}-kind`} label="Вид" className="w-36">
                    {(props) => (
                      <select
                        {...props}
                        value={item.kind}
                        onChange={(event) =>
                          patchForm(
                            updatePrescription(form, index, {
                              kind: event.target.value === 'procedure' ? 'procedure' : 'drug',
                            }),
                          )
                        }
                        className={controlClassName}
                      >
                        <option value="drug">Препарат</option>
                        <option value="procedure">Процедура</option>
                      </select>
                    )}
                  </Field>

                  <Field
                    id={`protocol-prescription-${index}-name`}
                    label="Название"
                    className="flex-1"
                    error={problemMessage(problems, `prescriptions[${index}].name`)}
                  >
                    {(props) => (
                      <input
                        {...props}
                        type="text"
                        value={item.name}
                        onChange={(event) =>
                          patchForm(
                            updatePrescription(form, index, { name: event.target.value }),
                          )
                        }
                        className={controlClassName}
                      />
                    )}
                  </Field>

                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => patchForm(removePrescription(form, index))}
                  >
                    Удалить
                  </Button>
                </div>

                {item.kind === 'drug' ? (
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Field id={`protocol-prescription-${index}-dose`} label="Дозировка">
                      {(props) => (
                        <input
                          {...props}
                          type="text"
                          value={item.dose}
                          placeholder="5 мг"
                          onChange={(event) =>
                            patchForm(
                              updatePrescription(form, index, { dose: event.target.value }),
                            )
                          }
                          className={controlClassName}
                        />
                      )}
                    </Field>
                    <Field id={`protocol-prescription-${index}-frequency`} label="Кратность">
                      {(props) => (
                        <input
                          {...props}
                          type="text"
                          value={item.frequency}
                          placeholder="1 раз в сутки"
                          onChange={(event) =>
                            patchForm(
                              updatePrescription(form, index, {
                                frequency: event.target.value,
                              }),
                            )
                          }
                          className={controlClassName}
                        />
                      )}
                    </Field>
                    <Field id={`protocol-prescription-${index}-duration`} label="Длительность">
                      {(props) => (
                        <input
                          {...props}
                          type="text"
                          value={item.duration}
                          placeholder="постоянно"
                          onChange={(event) =>
                            patchForm(
                              updatePrescription(form, index, {
                                duration: event.target.value,
                              }),
                            )
                          }
                          className={controlClassName}
                        />
                      )}
                    </Field>
                  </div>
                ) : null}

                {problemMessage(problems, `prescriptions[${index}]`) === null ? null : (
                  <p className="text-caption text-danger">
                    {problemMessage(problems, `prescriptions[${index}]`)}
                  </p>
                )}
              </div>
            ))}

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => patchForm(addPrescription(form, 'drug'))}>
                Добавить препарат
              </Button>
              <Button onClick={() => patchForm(addPrescription(form, 'procedure'))}>
                Добавить процедуру
              </Button>
            </div>
          </fieldset>
        </div>

        {/* Правая колонка закреплена: выбор клинрека и отправка не уезжают за экран */}
        <aside className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4 lg:sticky lg:top-4">
          <div className="flex flex-col gap-1">
            <span className="text-caption text-text-muted">Клинрек для проверки</span>
            {renderGuidelineField()}
            {guidelineError === null ? null : (
              <p id="protocol-guideline-error" className="text-caption text-danger">
                {guidelineError}
              </p>
            )}
          </div>

          {problems.length === 0 ? (
            <p className="text-caption text-text-muted">Форма заполнена, можно отправлять.</p>
          ) : (
            <p className="text-caption text-text-muted">
              Заполните обязательные поля: {problems.length}.
            </p>
          )}

          <Button
            type="submit"
            variant="primary"
            disabled={!canSubmit}
            className="w-full justify-center"
          >
            {validation.kind === 'loading' ? 'Проверяем форму…' : 'Проверить форму'}
          </Button>
        </aside>
      </form>

      {renderValidation()}
    </section>
  )
}

/** Подпись клинрека в списке выбора: название, версия и коды МКБ. */
function describeGuideline(guideline: Guideline): string {
  const codes = guideline.icd_codes ?? []
  const suffix = codes.length === 0 ? 'коды МКБ не указаны' : codes.join(', ')
  return `${guideline.title} · версия ${guideline.version} · ${suffix}`
}
