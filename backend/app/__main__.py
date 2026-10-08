"""Точка входа: ``python app/__main__.py`` — одинаково локально и в контейнере."""

import logging
import sys
from pathlib import Path

# При запуске файлом (а не пакетом) корень backend не попадает в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from app.config import get_settings
from app.main import app


def main() -> None:
    """Поднять сервер с настройками из окружения."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.backend.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        app,
        host=settings.backend.host,
        port=settings.backend.port,
        log_level=settings.backend.log_level.lower(),
    )


if __name__ == "__main__":
    main()
