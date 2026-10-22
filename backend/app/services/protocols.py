"""Валидация черновика протокола и раскладка формы на атомарные пункты.

Черновик не сохраняется: сервис только проверяет форму, подтверждает выбранный клинрек и
возвращает пункты, которые пойдут в проверку на соответствие клинреку.

Пункты строит сервер, а не клиент: тот же разбор понадобится при проверке, и два разных
набора пунктов в интерфейсе и в отчёте были бы ошибкой. Пункт — строка, потому что поле
`item` в будущем вердикте строковое.
"""

import logging

from app.schemas.guideline import Guideline, GuidelineStatus
from app.schemas.protocol import (
    IcdDiagnosis,
    ProtocolDraftRequest,
    ProtocolDraftResponse,
    ProtocolForm,
    ProtocolGuidelineRef,
    ProtocolPrescription,
)
from app.services.guidelines import GuidelineNotFoundError, GuidelineService
from app.services.icd import InvalidIcdCodeError, normalize_code

logger = logging.getLogger(__name__)

COMPLAINTS_MAX_CHARS = 5000
"""Предел жалоб: клинрек не читается по трёхстраничному тексту, а запрос не должен пухнуть."""

DESCRIPTION_MAX_CHARS = 5000
"""Предел описания диагноза."""

NAME_MAX_CHARS = 300
"""Предел названия диагноза и названия назначения."""

SHORT_MAX_CHARS = 100
"""Предел дозировки, кратности и длительности."""

PRESCRIPTIONS_MAX = 50
"""Сколько назначений принимается в одном протоколе."""


class ProtocolError(Exception):
    """Базовая ошибка работы с черновиком протокола."""


class ProtocolFormError(ProtocolError):
    """Форма не прошла проверку: поле названо, чтобы интерфейс мог его подсветить."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.reason = message


class GuidelineNotReadyError(ProtocolError):
    """Выбранный клинрек ещё не готов к проверке."""

    def __init__(self, guideline: Guideline) -> None:
        super().__init__(
            f"guideline {guideline.guideline_id} is {guideline.status.value}, "
            "only ready guidelines can be used"
        )
        self.guideline = guideline


def _require_text(value: str | None, field: str, limit: int) -> str:
    """Потребовать непустой текст в пределах длины и вернуть его без краевых пробелов."""
    text = (value or "").strip()
    if not text:
        raise ProtocolFormError(field, "value is required")
    if len(text) > limit:
        raise ProtocolFormError(field, f"value is longer than {limit} characters")
    return text


def _optional_text(value: str | None, field: str, limit: int) -> str | None:
    """Необязательный текст: пустой остаётся пустым, длинный — отклоняется."""
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > limit:
        raise ProtocolFormError(field, f"value is longer than {limit} characters")
    return text


def _validate_diagnosis(diagnosis: IcdDiagnosis) -> IcdDiagnosis:
    """Проверить и нормализовать диагноз: код МКБ и название."""
    try:
        code = normalize_code(diagnosis.code)
    except InvalidIcdCodeError as exc:
        raise ProtocolFormError("diagnosis.code", "expected ICD-10 code, for example I10") from exc
    name = _require_text(diagnosis.name, "diagnosis.name", NAME_MAX_CHARS)
    return IcdDiagnosis(code=code, name=name)


def _validate_prescription(index: int, item: ProtocolPrescription) -> ProtocolPrescription:
    """Проверить одно назначение: название обязательно, дозировка — только у препарата."""
    prefix = f"prescriptions[{index}]"
    name = _require_text(item.name, f"{prefix}.name", NAME_MAX_CHARS)
    dose = _optional_text(item.dose, f"{prefix}.dose", SHORT_MAX_CHARS)
    frequency = _optional_text(item.frequency, f"{prefix}.frequency", SHORT_MAX_CHARS)
    duration = _optional_text(item.duration, f"{prefix}.duration", SHORT_MAX_CHARS)
    if item.kind == "procedure" and any(
        value is not None for value in (dose, frequency, duration)
    ):
        raise ProtocolFormError(
            prefix, "dose, frequency and duration are allowed for drugs only"
        )
    return ProtocolPrescription(
        kind=item.kind,
        name=name,
        dose=dose,
        frequency=frequency,
        duration=duration,
    )


def validate_form(form: ProtocolForm) -> ProtocolForm:
    """Проверить форму и вернуть её нормализованной.

    Отказ называет поле: интерфейс подсвечивает именно его, а не показывает общее «форма
    неверна».
    """
    complaints = _require_text(form.complaints, "complaints", COMPLAINTS_MAX_CHARS)
    diagnosis = _validate_diagnosis(form.diagnosis)
    description = _optional_text(
        form.diagnosis_description, "diagnosis_description", DESCRIPTION_MAX_CHARS
    )
    if len(form.prescriptions) > PRESCRIPTIONS_MAX:
        raise ProtocolFormError(
            "prescriptions", f"more than {PRESCRIPTIONS_MAX} prescriptions"
        )
    prescriptions = [
        _validate_prescription(index, item) for index, item in enumerate(form.prescriptions)
    ]
    return ProtocolForm(
        complaints=complaints,
        diagnosis=diagnosis,
        diagnosis_description=description,
        prescriptions=prescriptions,
    )


def build_statements(form: ProtocolForm) -> list[str]:
    """Разложить форму на атомарные пункты в детерминированном порядке.

    Порядок — жалобы, диагноз, необязательное описание, затем назначения по одному пункту
    на каждое: два препарата не должны склеиться в одно утверждение, иначе вердикт по ним
    будет один на двоих.
    """
    statements = [
        f"Жалобы: {form.complaints}",
        f"Диагноз: {form.diagnosis.code} — {form.diagnosis.name}",
    ]
    if form.diagnosis_description:
        statements.append(f"Описание диагноза: {form.diagnosis_description}")
    for item in form.prescriptions:
        if item.kind == "drug":
            parts = (item.name, item.dose, item.frequency, item.duration)
            details = [part for part in parts if part]
            statements.append(f"Назначение: {', '.join(details)}")
        else:
            statements.append(f"Процедура: {item.name}")
    return statements


class ProtocolService:
    """Валидация черновика протокола против выбранного клинрека."""

    def __init__(self, guidelines: GuidelineService) -> None:
        self._guidelines = guidelines

    def validate(self, draft: ProtocolDraftRequest) -> ProtocolDraftResponse:
        """Проверить форму и подтвердить выбранный клинрек.

        Форма проверяется первой: она не зависит от хранилища, а `400` по ней полезнее, чем
        `404` по клинреку, который указан неверно.
        """
        form = validate_form(draft.form)
        try:
            guideline = self._guidelines.get(draft.guideline_id, draft.guideline_version)
        except GuidelineNotFoundError:
            raise
        if guideline.status is not GuidelineStatus.READY:
            raise GuidelineNotReadyError(guideline)

        statements = build_statements(form)
        logger.info(
            "Protocol draft validated: guideline=%s statements=%d",
            guideline.guideline_id,
            len(statements),
        )
        return ProtocolDraftResponse(
            guideline=_guideline_ref(guideline),
            form=form,
            statements=statements,
        )


def _guideline_ref(guideline: Guideline) -> ProtocolGuidelineRef:
    """Сведения о клинреке для ответа валидации."""
    return ProtocolGuidelineRef(
        guideline_id=guideline.guideline_id,
        version=guideline.version,
        title=guideline.title,
        status=guideline.status,
        icd_codes=list(guideline.icd_codes),
    )
