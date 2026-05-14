from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import Settings


def setup_logging(settings: Settings) -> None:
    """Configure console and file logging."""

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        backtrace=True,
        diagnose=False,
        enqueue=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    output_dir = Path(settings.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        output_dir / "paper_info_crawler.log",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
