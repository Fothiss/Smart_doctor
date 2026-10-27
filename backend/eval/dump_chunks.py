"""Одноразовый дамп чанков клинрека из векторного хранилища.

Нужен разметке эталонного набора: ожидаемый фрагмент кейса — это ``chunk_id``, а
перечисления чанков в API нет (только чтение по идентификатору). Скрипт читает
коллекцию целиком и складывает рядом два файла: ``chunk_dump.json`` — машинный вход
разметки, ``chunk_dump.md`` — читаемую выжимку по разделам для выбора фрагментов.

Запускать при остановленном бэкенде: локальный Qdrant держит каталог заблокированным.
"""

import json
import sys
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""Корень ``backend``: при запуске файлом он не попадает в ``sys.path``."""

from app.clients.vector_store import create_client  # noqa: E402
from app.config import get_settings  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
DUMP_JSON = EVAL_DIR / "chunk_dump.json"
DUMP_MD = EVAL_DIR / "chunk_dump.md"
SCROLL_LIMIT = 256
"""Сколько точек забирать за один проход: у Qdrant это страница, а не весь набор."""

NO_SECTION = "без раздела"


def iter_payloads(client: Any, collection: str) -> Iterator[dict[str, Any]]:
    """Пройти по всем точкам коллекции, отдавая payload по одной.

    ``scroll`` — единственный способ перечислить хранилище: у поиска есть запрос и
    лимит, а полный обход нужен именно здесь.
    """
    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=SCROLL_LIMIT,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            if point.payload:
                yield point.payload
        if offset is None:
            return


def dump(chunks: list[dict[str, Any]]) -> None:
    """Записать JSON и markdown-выжимку по собранным чанкам."""
    chunks.sort(key=lambda chunk: (str(chunk.get("guideline_id")), chunk.get("chunk_index", 0)))
    DUMP_JSON.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_section[chunk.get("section") or NO_SECTION].append(chunk)

    lines = [
        "# Чанки клинрека",
        "",
        f"Всего: {len(chunks)}; разделов: {len(by_section)}. "
        "Собрано `dump_chunks.py`, править руками не нужно.",
        "",
    ]
    for section, section_chunks in by_section.items():
        lines.append(f"## {section} ({len(section_chunks)})")
        lines.append("")
        for chunk in section_chunks:
            lines.append(
                f"### [{chunk.get('chunk_index')}] стр. {chunk.get('page')} — "
                f"`{chunk.get('chunk_id')}`"
            )
            lines.append("")
            lines.append(" ".join(str(chunk.get("text", "")).split()))
            lines.append("")
    DUMP_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Прочитать хранилище и записать дамп."""
    settings = get_settings()
    store = create_client(settings.database)
    collection = f"{settings.database.qdrant_collection}__{settings.embedding.dimension}"
    try:
        if not store.collection_exists(collection):
            raise SystemExit(f"collection {collection} does not exist: index a guideline first")
        chunks = list(iter_payloads(store, collection))
    finally:
        store.close()

    if not chunks:
        raise SystemExit(f"collection {collection} is empty")
    dump(chunks)
    print(f"Wrote {len(chunks)} chunks to {DUMP_JSON} and {DUMP_MD}")


if __name__ == "__main__":
    main()
