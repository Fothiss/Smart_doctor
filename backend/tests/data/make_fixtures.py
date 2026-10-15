"""Генератор PDF-фикстур для тестов.

Фикстуры — настоящие PDF, а не файл с сигнатурой ``%PDF-``: извлекать строки и
координаты можно только из разбираемого документа. Кириллица в такой файл без
встроенного шрифта не помещается, поэтому текст фикстур латинский: тесты проверяют
структуру (страницы, координаты, абзацы, заголовки), а не язык.

Запуск (из ``backend/``)::

    .venv/Scripts/python.exe tests/data/make_fixtures.py
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
LINE_HEIGHT = 16


def _text_block(lines: list[str], *, font_size: int = 12, start_y: int = 770) -> str:
    """Собрать поток содержимого страницы с текстом построчно."""
    commands = ["BT", f"/F1 {font_size} Tf", "14 TL"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        commands.append(f"1 0 0 1 72 {start_y - index * LINE_HEIGHT} Tm ({escaped}) Tj")
    commands.append("ET")
    return "\n".join(commands)


def _build_pdf(pages: list[tuple[str, int]]) -> bytes:
    """Собрать PDF: каталог, страницы с общим шрифтом и таблица ссылок."""
    font_object = 3
    page_objects: list[tuple[int, int]] = []
    next_number = 4
    for _ in pages:
        page_objects.append((next_number, next_number + 1))
        next_number += 2

    body = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add(number: int, payload: bytes) -> None:
        offsets[number] = len(body)
        body.extend(payload)

    kids = " ".join(f"{page} 0 R" for page, _ in page_objects)
    add(1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add(
        2,
        f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>\nendobj\n".encode(),
    )
    add(
        font_object,
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    )

    for (page_number, content_number), (content, rotation) in zip(page_objects, pages, strict=True):
        add(
            page_number,
            (
                f"{page_number} 0 obj\n"
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_object} 0 R >> >> "
                f"/Contents {content_number} 0 R /Rotate {rotation} >>\n"
                "endobj\n"
            ).encode(),
        )
        payload = content.encode("latin-1", "replace")
        add(
            content_number,
            f"{content_number} 0 obj\n<< /Length {len(payload)} >>\nstream\n".encode()
            + payload
            + b"\nendstream\nendobj\n",
        )

    xref_offset = len(body)
    total = max(offsets) + 1
    body.extend(f"xref\n0 {total}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for number in range(1, total):
        body.extend(f"{offsets.get(number, 0):010d} 00000 n \n".encode())
    body.extend(
        f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(body)


MINI_PAGES = [
    (_text_block(["Clinical guidelines", "Arterial hypertension"]), 0),
    (
        _text_block(
            [
                "Contents",
                "1. Definition ................... 3",
                "1.1 Etiology ................... 3",
                "2. Diagnostics ................. 4",
            ]
        ),
        0,
    ),
    (
        _text_block(
            [
                "1. Definition",
                "Hypertension is a persistent elevation of blood pressure.",
                "",
                "1.1 Etiology",
                "The cause is unknown in most cases.",
                "Such cases are called primary hypertension.",
                "Secondary forms are caused by renal disease",
                "or by an endocrine or vascular disorder.",
                "",
                "Long paragraph follows to make the splitter cut it by sentences.",
                "First sentence of the long paragraph speaks about measurement.",
                "Second sentence continues the thought about target values.",
                "Third sentence mentions office and home blood pressure.",
            ]
        ),
        0,
    ),
    (
        _text_block(
            [
                "2. Diagnostics",
                "Measure blood pressure on both arms at every visit.",
                "Confirm the diagnosis with home monitoring.",
            ]
        ),
        90,
    ),
]

EMPTY_PAGES = [("", 0), ("", 0)]


def main() -> None:
    """Записать фикстуры рядом со скриптом."""
    (DATA_DIR / "mini.pdf").write_bytes(_build_pdf(MINI_PAGES))
    (DATA_DIR / "scanned.pdf").write_bytes(_build_pdf(EMPTY_PAGES))
    print(f"written: {DATA_DIR / 'mini.pdf'}, {DATA_DIR / 'scanned.pdf'}")


if __name__ == "__main__":
    main()
