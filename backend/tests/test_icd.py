"""Проверки правил кодов МКБ-10: формат, нормализация и сопоставление."""

import pytest

from app.services.icd import (
    InvalidIcdCodeError,
    matches_icd,
    normalize_code,
    normalize_codes,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("I10", "I10"),
        (" i10.1 ", "I10.1"),
        ("j06", "J06"),
        ("M54.5", "M54.5"),
    ],
)
def test_normalize_code_uppercases_and_strips(raw: str, expected: str) -> None:
    assert normalize_code(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "10", "I1", "I100", "гипертензия", "I10."])
def test_normalize_code_rejects_anything_outside_format(raw: str) -> None:
    with pytest.raises(InvalidIcdCodeError) as excinfo:
        normalize_code(raw)

    assert excinfo.value.code == raw


def test_normalize_codes_drops_duplicates_and_keeps_order() -> None:
    assert normalize_codes([" i15 ", "I10", "i10", ""]) == ("I15", "I10")


def test_normalize_codes_of_empty_input_is_empty() -> None:
    assert normalize_codes([]) == ()
    assert normalize_codes(["", "  "]) == ()


def test_normalize_codes_rejects_invalid_member() -> None:
    with pytest.raises(InvalidIcdCodeError):
        normalize_codes(["I10", "не код"])


@pytest.mark.parametrize(
    ("stored", "query", "expected"),
    [
        ("I10", "I10", True),
        ("I10", "I10.1", True),
        ("I10.1", "I10", True),
        ("I10.1", "I10.2", False),
        ("I10", "I11", False),
        ("I10", "I1", False),
        ("J06", "I10", False),
    ],
)
def test_matches_icd_compares_by_segment(
    stored: str, query: str, expected: bool
) -> None:
    assert matches_icd(stored, query) is expected
