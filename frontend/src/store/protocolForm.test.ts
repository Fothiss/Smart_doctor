import { describe, expect, it } from 'vitest'

import {
  addPrescription,
  canValidate,
  draftProblems,
  emptyProtocolForm,
  hasProblem,
  removePrescription,
  toDraftRequest,
  updatePrescription,
} from './protocolForm'

/** Заполненная форма с одним препаратом. */
function filledForm() {
  const form = {
    ...emptyProtocolForm(),
    complaints: 'Головная боль',
    icdCode: 'i10',
    diagnosisName: 'Гипертензия',
    diagnosisDescription: 'АГ 2 ст.',
  }
  return updatePrescription(addPrescription(form), 0, {
    name: 'Амлодипин',
    dose: '5 мг',
    frequency: '1 раз в сутки',
  })
}

describe('назначения', () => {
  it('добавляются в конец отдельными пунктами', () => {
    const form = addPrescription(addPrescription(emptyProtocolForm(), 'drug'), 'procedure')

    expect(form.prescriptions).toHaveLength(2)
    expect(form.prescriptions[1]?.kind).toBe('procedure')
  })

  it('удаляются по индексу, остальные не меняются', () => {
    const form = updatePrescription(addPrescription(emptyProtocolForm()), 0, { name: 'ЭКГ' })
    const withTwo = addPrescription(form, 'procedure')

    const trimmed = removePrescription(updatePrescription(withTwo, 1, { name: 'ОАК' }), 0)

    expect(trimmed.prescriptions).toHaveLength(1)
    expect(trimmed.prescriptions[0]?.name).toBe('ОАК')
  })

  it('изменение одного пункта не трогает другой', () => {
    const form = addPrescription(addPrescription(emptyProtocolForm()), 'procedure')

    const updated = updatePrescription(form, 1, { name: 'ЭКГ' })

    expect(updated.prescriptions[0]?.name).toBe('')
    expect(updated.prescriptions[1]?.name).toBe('ЭКГ')
  })
})

describe('draftProblems', () => {
  it('пустая форма перечисляет обязательные поля', () => {
    const fields = draftProblems(emptyProtocolForm()).map((problem) => problem.field)

    expect(fields).toEqual(['complaints', 'diagnosis.code', 'diagnosis.name'])
  })

  it('неверный формат кода — проблема поля кода', () => {
    const form = updatePrescription(filledForm(), 0, {})

    expect(hasProblem(draftProblems(form), 'diagnosis.code')).toBe(false)
    expect(
      hasProblem(draftProblems({ ...filledForm(), icdCode: 'гипертензия' }), 'diagnosis.code'),
    ).toBe(true)
  })

  it('пустое название назначения — проблема своего пункта', () => {
    const form = updatePrescription(filledForm(), 0, { name: '  ' })

    expect(hasProblem(draftProblems(form), 'prescriptions[0].name')).toBe(true)
  })

  it('дозировка у процедуры — проблема пункта', () => {
    const form = updatePrescription(filledForm(), 0, { kind: 'procedure', dose: '5 мг' })

    expect(hasProblem(draftProblems(form), 'prescriptions[0]')).toBe(true)
  })

  it('заполненная форма проблем не имеет', () => {
    expect(draftProblems(filledForm())).toEqual([])
  })
})

describe('canValidate', () => {
  it('без выбранного клинрека отправка недоступна', () => {
    expect(canValidate(filledForm(), null)).toBe(false)
  })

  it('с клинреком и корректной формой отправка доступна', () => {
    expect(canValidate(filledForm(), 'guideline-id')).toBe(true)
  })

  it('с ошибками формы отправка недоступна даже с клинреком', () => {
    expect(canValidate(emptyProtocolForm(), 'guideline-id')).toBe(false)
  })
})

describe('toDraftRequest', () => {
  it('собирает запрос с нормализованным кодом и пустыми необязательными полями', () => {
    const request = toDraftRequest(filledForm(), 'guideline-id')

    expect(request.guideline_id).toBe('guideline-id')
    expect(request.form.diagnosis).toEqual({ code: 'I10', name: 'Гипертензия' })
    expect(request.form.diagnosis_description).toBe('АГ 2 ст.')
    expect(request.form.prescriptions).toEqual([
      {
        kind: 'drug',
        name: 'Амлодипин',
        dose: '5 мг',
        frequency: '1 раз в сутки',
        duration: undefined,
      },
    ])
  })

  it('не отправляет дозировку у процедуры', () => {
    const form = updatePrescription(filledForm(), 0, {
      kind: 'procedure',
      name: 'ЭКГ',
      dose: '5 мг',
      frequency: '1 раз в сутки',
      duration: 'месяц',
    })

    expect(toDraftRequest(form, 'guideline-id').form.prescriptions).toEqual([
      { kind: 'procedure', name: 'ЭКГ' },
    ])
  })

  it('пустое описание диагноза не попадает в запрос', () => {
    const request = toDraftRequest({ ...filledForm(), diagnosisDescription: '  ' }, 'id')

    expect(request.form.diagnosis_description).toBeUndefined()
  })
})
