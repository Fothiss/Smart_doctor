"""Проверки валидации черновика протокола: форма, пункты, привязка к клинреку."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.guideline import Guideline, GuidelineStatus
from app.schemas.protocol import (
    IcdDiagnosis,
    ProtocolDraftRequest,
    ProtocolForm,
    ProtocolPrescription,
)
from app.services.guidelines import GuidelineNotFoundError, GuidelineService
from app.services.protocols import (
    COMPLAINTS_MAX_CHARS,
    PRESCRIPTIONS_MAX,
    GuidelineNotReadyError,
    ProtocolFormError,
    ProtocolService,
    build_statements,
    validate_form,
)

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _write_guideline(
    guidelines_dir: Path,
    *,
    status: GuidelineStatus = GuidelineStatus.READY,
    icd_codes: list[str] | None = None,
) -> Guideline:
    """Положить клинрек в хранилище вручную с нужным статусом."""
    guideline_id = uuid4()
    directory = guidelines_dir / str(guideline_id)
    directory.mkdir(parents=True)
    (directory / "original.pdf").write_bytes(PDF_BYTES)
    guideline = Guideline(
        guideline_id=guideline_id,
        version=1,
        title="Гипертензия",
        filename="klinrek.pdf",
        size_bytes=len(PDF_BYTES),
        sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        status=status,
        created_at=datetime.now(UTC),
        icd_codes=icd_codes or ["I10"],
    )
    (directory / "meta.json").write_text(guideline.model_dump_json(), encoding="utf-8")
    return guideline


def _form(**overrides: object) -> ProtocolForm:
    """Заполненная форма с возможностью заменить отдельные поля."""
    base: dict[str, object] = {
        "complaints": "Головная боль, головокружение",
        "diagnosis": IcdDiagnosis(code="i10", name=" Гипертензия "),
        "prescriptions": [
            ProtocolPrescription(
                kind="drug", name="Амлодипин", dose="5 мг", frequency="1 раз в сутки"
            )
        ],
    }
    base.update(overrides)
    return ProtocolForm(**base)


def _draft(guideline_id: object, form: ProtocolForm | None = None) -> ProtocolDraftRequest:
    return ProtocolDraftRequest(guideline_id=guideline_id, form=form or _form())


def test_validate_form_normalizes_code_and_texts() -> None:
    form = validate_form(_form())

    assert form.diagnosis.code == "I10"
    assert form.diagnosis.name == "Гипертензия"
    assert form.diagnosis_description is None


def test_validate_form_rejects_empty_complaints() -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(_form(complaints="   "))

    assert excinfo.value.field == "complaints"
    assert "required" in excinfo.value.reason


def test_validate_form_rejects_too_long_complaints() -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(_form(complaints="я" * (COMPLAINTS_MAX_CHARS + 1)))

    assert excinfo.value.field == "complaints"


@pytest.mark.parametrize("code", ["10", "I1", "гипертензия", ""])
def test_validate_form_rejects_bad_icd_code(code: str) -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(_form(diagnosis=IcdDiagnosis(code=code, name="Гипертензия")))

    assert excinfo.value.field == "diagnosis.code"


def test_validate_form_rejects_empty_diagnosis_name() -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(_form(diagnosis=IcdDiagnosis(code="I10", name="  ")))

    assert excinfo.value.field == "diagnosis.name"


def test_validate_form_rejects_empty_prescription_name() -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(
            _form(prescriptions=[ProtocolPrescription(kind="procedure", name="  ")])
        )

    assert excinfo.value.field == "prescriptions[0].name"


def test_validate_form_rejects_dose_on_procedure() -> None:
    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(
            _form(prescriptions=[ProtocolPrescription(kind="procedure", name="ЭКГ", dose="1")])
        )

    assert excinfo.value.field == "prescriptions[0]"
    assert "drugs only" in excinfo.value.reason


def test_validate_form_rejects_too_many_prescriptions() -> None:
    items = [
        ProtocolPrescription(kind="procedure", name=f"Процедура {index}")
        for index in range(PRESCRIPTIONS_MAX + 1)
    ]

    with pytest.raises(ProtocolFormError) as excinfo:
        validate_form(_form(prescriptions=items))

    assert excinfo.value.field == "prescriptions"


def test_validate_form_allows_empty_prescriptions() -> None:
    assert validate_form(_form(prescriptions=[])).prescriptions == []


def test_build_statements_keeps_one_claim_per_prescription() -> None:
    form = _form(
        diagnosis_description="АГ 2 ст., риск 3",
        prescriptions=[
            ProtocolPrescription(
                kind="drug", name="Амлодипин", dose="5 мг", frequency="1 раз в сутки"
            ),
            ProtocolPrescription(kind="drug", name="Эналаприл", dose="10 мг"),
            ProtocolPrescription(kind="procedure", name="ЭКГ"),
        ],
    )

    assert build_statements(validate_form(form)) == [
        "Жалобы: Головная боль, головокружение",
        "Диагноз: I10 — Гипертензия",
        "Описание диагноза: АГ 2 ст., риск 3",
        "Назначение: Амлодипин, 5 мг, 1 раз в сутки",
        "Назначение: Эналаприл, 10 мг",
        "Процедура: ЭКГ",
    ]


def test_build_statements_skips_empty_description() -> None:
    statements = build_statements(validate_form(_form(prescriptions=[])))

    assert statements == ["Жалобы: Головная боль, головокружение", "Диагноз: I10 — Гипертензия"]


def test_service_returns_normalized_draft(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_guideline(guidelines_dir)
    protocol = ProtocolService(service)

    response = protocol.validate(_draft(guideline.guideline_id))

    assert response.guideline.guideline_id == guideline.guideline_id
    assert response.guideline.title == "Гипертензия"
    assert response.guideline.icd_codes == ["I10"]
    assert response.form.diagnosis.code == "I10"
    assert response.statements[-1] == "Назначение: Амлодипин, 5 мг, 1 раз в сутки"


def test_service_rejects_unknown_guideline(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)

    with pytest.raises(GuidelineNotFoundError):
        ProtocolService(service).validate(_draft(uuid4()))


def test_service_rejects_guideline_that_is_not_ready(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_guideline(guidelines_dir, status=GuidelineStatus.UPLOADED)

    with pytest.raises(GuidelineNotReadyError) as excinfo:
        ProtocolService(service).validate(_draft(guideline.guideline_id))

    assert excinfo.value.guideline.guideline_id == guideline.guideline_id


def test_service_rejects_version_mismatch(guidelines_dir: Path) -> None:
    service = GuidelineService(guidelines_dir, max_upload_size_bytes=1024)
    guideline = _write_guideline(guidelines_dir)

    with pytest.raises(GuidelineNotFoundError):
        ProtocolService(service).validate(
            ProtocolDraftRequest(
                guideline_id=guideline.guideline_id, guideline_version=2, form=_form()
            )
        )
