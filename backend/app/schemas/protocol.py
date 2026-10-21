"""Схемы черновика врачебного протокола.

Схемы описывают только структуру. Правила содержимого — обязательность, длины и формат
кода МКБ — проверяет сервис, чтобы отказ приходил как `400` с именем отклонённого поля, а
не как автоматический `422` от валидации тела запроса.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.guideline import GuidelineStatus


class IcdDiagnosis(BaseModel):
    """Диагноз протокола: код МКБ-10 и его название.

    Название вводится руками: справочника МКБ пока нет, поэтому код и название хранятся
    вместе и не выводятся друг из друга.
    """

    code: str = Field(description="Код МКБ-10, например I10 или I10.1")
    name: str = Field(description="Название диагноза как его записал врач")


class ProtocolPrescription(BaseModel):
    """Назначение: препарат или процедура.

    Дозировка, кратность и длительность описывают препарат; для процедуры они запрещены —
    иначе сервер молча принимает бессмысленные данные.
    """

    kind: Literal["drug", "procedure"] = Field(description="Вид назначения")
    name: str = Field(description="Название препарата или процедуры")
    dose: str | None = Field(default=None, description="Дозировка; только для препарата")
    frequency: str | None = Field(default=None, description="Кратность; только для препарата")
    duration: str | None = Field(default=None, description="Длительность; только для препарата")


class ProtocolForm(BaseModel):
    """Заполненная форма протокола без привязки к клинреку."""

    complaints: str = Field(description="Жалобы")
    diagnosis: IcdDiagnosis
    diagnosis_description: str | None = Field(
        default=None, description="Описание диагноза: степень, риск, течение"
    )
    prescriptions: list[ProtocolPrescription] = Field(
        default_factory=list, description="Назначения отдельными пунктами"
    )


class ProtocolDraftRequest(BaseModel):
    """Черновик протокола, который присылает интерфейс."""

    guideline_id: UUID = Field(description="Клинрек, по которому будет проверка")
    guideline_version: int | None = Field(
        default=None, ge=1, description="Версия документа; по умолчанию последняя"
    )
    form: ProtocolForm


class ProtocolGuidelineRef(BaseModel):
    """Сведения о выбранном клинреке, подтверждённые сервером."""

    guideline_id: UUID
    version: int = Field(ge=1)
    title: str
    status: GuidelineStatus
    icd_codes: list[str] = Field(
        default_factory=list, description="Коды МКБ-10, которые покрывает клинрек"
    )


class ProtocolDraftResponse(BaseModel):
    """Подтверждённый черновик и пункты, которые пойдут в проверку.

    Ответ не содержит идентификатора протокола: черновик не сохраняется.
    """

    guideline: ProtocolGuidelineRef
    form: ProtocolForm
    statements: list[str] = Field(
        description="Атомарные пункты протокола в порядке формы: жалобы, диагноз, назначения"
    )
