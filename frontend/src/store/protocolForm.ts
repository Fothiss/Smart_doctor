/**
 * Черновик формы протокола: состояние полей и подготовка запроса.
 *
 * Логика вынесена из экрана: правила полей, добавление и удаление назначений и сборка
 * запроса проверяются тестом без DOM, а сам экран остаётся разметкой.
 */

import type { ProtocolDraftRequest, ProtocolPrescription } from '../api/protocols'
import { normalizeIcd } from '../lib/icd'

/** Назначение в том виде, в каком его заполняют: пустые поля остаются строками. */
export type PrescriptionDraft = {
  kind: 'drug' | 'procedure'
  name: string
  dose: string
  frequency: string
  duration: string
}

/** Форма протокола в состоянии экрана. */
export type ProtocolFormDraft = {
  complaints: string
  icdCode: string
  diagnosisName: string
  diagnosisDescription: string
  prescriptions: PrescriptionDraft[]
}

/** Проблема формы: имя поля нужно, чтобы подсветить именно его. */
export type FormProblem = {
  field: string
  message: string
}

/** Пустая форма: назначений нет, пока врач не добавит первое. */
export function emptyProtocolForm(): ProtocolFormDraft {
  return {
    complaints: '',
    icdCode: '',
    diagnosisName: '',
    diagnosisDescription: '',
    prescriptions: [],
  }
}

/** Пустое назначение-препарат: вид по умолчанию — то, что назначают чаще. */
export function emptyPrescription(kind: 'drug' | 'procedure' = 'drug'): PrescriptionDraft {
  return { kind, name: '', dose: '', frequency: '', duration: '' }
}

/** Добавить назначение в конец формы. */
export function addPrescription(
  form: ProtocolFormDraft,
  kind: 'drug' | 'procedure' = 'drug',
): ProtocolFormDraft {
  return { ...form, prescriptions: [...form.prescriptions, emptyPrescription(kind)] }
}

/** Удалить назначение по индексу; остальные пункты не меняются. */
export function removePrescription(form: ProtocolFormDraft, index: number): ProtocolFormDraft {
  return {
    ...form,
    prescriptions: form.prescriptions.filter((_, position) => position !== index),
  }
}

/** Изменить одно назначение, не трогая остальные. */
export function updatePrescription(
  form: ProtocolFormDraft,
  index: number,
  patch: Partial<PrescriptionDraft>,
): ProtocolFormDraft {
  return {
    ...form,
    prescriptions: form.prescriptions.map((item, position) =>
      position === index ? { ...item, ...patch } : item,
    ),
  }
}

/** Ошибки формы: те же правила, что проверяет сервер, но до отправки. */
export function draftProblems(form: ProtocolFormDraft): FormProblem[] {
  const problems: FormProblem[] = []
  if (form.complaints.trim() === '') {
    problems.push({ field: 'complaints', message: 'Жалобы обязательны' })
  }
  if (normalizeIcd(form.icdCode) === null) {
    problems.push({ field: 'diagnosis.code', message: 'Код МКБ-10 обязателен' })
  }
  if (form.diagnosisName.trim() === '') {
    problems.push({ field: 'diagnosis.name', message: 'Название диагноза обязательно' })
  }
  form.prescriptions.forEach((item, index) => {
    if (item.name.trim() === '') {
      problems.push({
        field: `prescriptions[${index}].name`,
        message: 'Название назначения обязательно',
      })
    }
    if (item.kind === 'procedure' && (item.dose || item.frequency || item.duration)) {
      problems.push({
        field: `prescriptions[${index}]`,
        message: 'Дозировка и кратность указываются только для препаратов',
      })
    }
  })
  return problems
}

/** Есть ли проблема у поля (или у его части). */
export function hasProblem(problems: readonly FormProblem[], field: string): boolean {
  return problems.some((problem) => problem.field === field)
}

/** Сообщение об ошибке именно этого поля; `null` — поле в порядке. */
export function problemMessage(
  problems: readonly FormProblem[],
  field: string,
): string | null {
  return problems.find((problem) => problem.field === field)?.message ?? null
}

/** Первое поле с ошибкой: при отправке фокус уходит именно туда. */
export function firstInvalidField(problems: readonly FormProblem[]): string | null {
  return problems[0]?.field ?? null
}

/** Можно ли отправлять черновик: выбран клинрек и форма без ошибок. */
export function canValidate(
  form: ProtocolFormDraft,
  guidelineId: string | null,
): boolean {
  return guidelineId !== null && draftProblems(form).length === 0
}

/** Собрать запрос к серверу: пустые необязательные поля в него не попадают. */
export function toDraftRequest(
  form: ProtocolFormDraft,
  guidelineId: string,
): ProtocolDraftRequest {
  return {
    guideline_id: guidelineId,
    form: {
      complaints: form.complaints.trim(),
      diagnosis: {
        code: normalizeIcd(form.icdCode) ?? form.icdCode.trim(),
        name: form.diagnosisName.trim(),
      },
      diagnosis_description: optionalField(form.diagnosisDescription),
      prescriptions: form.prescriptions.map(toPrescription),
    },
  }
}

function toPrescription(item: PrescriptionDraft): ProtocolPrescription {
  if (item.kind === 'procedure') {
    // Дозировка процедуре не принадлежит: сервер отклонит такое назначение
    return { kind: 'procedure', name: item.name.trim() }
  }
  return {
    kind: 'drug',
    name: item.name.trim(),
    dose: optionalField(item.dose),
    frequency: optionalField(item.frequency),
    duration: optionalField(item.duration),
  }
}

function optionalField(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed === '' ? undefined : trimmed
}
