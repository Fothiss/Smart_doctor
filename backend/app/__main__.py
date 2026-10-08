"""Точка входа: ``python app/__main__.py`` — одинаково локально и в контейнере."""

import logging
import sys
from pathlib import Path

# При запуске файлом (а не пакетом) корень backend не попадает в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
 

def main() -> None:
    """Поднять сервер с настройками из окружения."""
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
