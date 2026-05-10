from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


_LOGGING_CONFIGURED = False


def configure_logging(level: str = "INFO", log_dir: str | Path = "logs") -> None:
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    file_handler = logging.FileHandler(
        path / f"tech_watch_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
