import sys
from contextvars import ContextVar

from loguru import logger

from app.config import get_settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def _patch_record(record):
    record["extra"]["request_id"] = request_id_var.get()


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, serialize=True, level=get_settings().LOG_LEVEL)
    logger.configure(patcher=_patch_record)