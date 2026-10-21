"""Правила кодов МКБ-10: проверка формата, нормализация и сопоставление.

Модуль чистый: ни FastAPI, ни диска, ни настроек. Одни и те же правила нужны при
загрузке клинрека, при фильтрации библиотеки и при валидации диагноза протокола,
поэтому они живут здесь, а не в схемах и не в роутерах.
"""

import re
from collections.abc import Iterable

ICD_CODE_PATTERN = r"^[A-Z]\d{2}(\.\d{1,2})?$"
"""Код МКБ-10: заглавная латинская буква, две цифры и необязательное уточнение."""

_CODE = re.compile(ICD_CODE_PATTERN)

ICD_CODE_EXAMPLE = "I10"
"""Пример кода для сообщений об ошибке."""


class InvalidIcdCodeError(ValueError):
    """Код не соответствует формату МКБ-10."""

    def __init__(self, code: str) -> None:
        super().__init__(f"invalid ICD code: {code!r}")
        self.code = code


def normalize_code(raw: str) -> str:
    """Привести код к каноническому виду: обрезать края и поднять регистр.

    Пример в сообщении об ошибке должен показывать именно то, что пришло, поэтому
    исключение получает исходную строку.
    """
    code = raw.strip().upper()
    if not _CODE.fullmatch(code):
        raise InvalidIcdCodeError(raw)
    return code


def normalize_codes(raw_codes: Iterable[str]) -> tuple[str, ...]:
    """Нормализовать коды и убрать повторы, сохранив порядок первого появления.

    Пустые строки отбрасываются: лишняя запятая в интерфейсе — не повод отказать.
    """
    unique: dict[str, None] = {}
    for raw in raw_codes:
        if not raw.strip():
            continue
        unique.setdefault(normalize_code(raw), None)
    return tuple(unique)


def matches_icd(stored: str, query: str) -> bool:
    """Совпадает ли код клинрека с кодом-фильтром с учётом уточнения.

    Код клинрека ``I10`` совпадает с фильтром ``I10`` и ``I10.1``, а ``I10.1`` —
    с фильтром ``I10``. Сравнение идёт по границе сегмента: ``I1`` не совпадает с
    ``I10``, хотя и является его префиксом.
    """
    return (
        stored == query
        or stored.startswith(f"{query}.")
        or query.startswith(f"{stored}.")
    )
