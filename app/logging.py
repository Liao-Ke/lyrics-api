import sys

from loguru import logger

from app.config import get_settings


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, serialize=True, level=get_settings().LOG_LEVEL)