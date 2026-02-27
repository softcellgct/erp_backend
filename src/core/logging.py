"""
Centralized logging configuration.

Usage: `from core.logging import logger`
"""

import logging
import os
import sys

from loguru import logger

# ── Paths ─────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
os.makedirs(LOG_DIR, exist_ok=True)

# ── Format ────────────────────────────────────────────
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level:<8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - "
    "<level>{message}</level>"
)

# Reset default handlers
logger.remove()

# Console
logger.add(
    sys.stderr,
    format=LOG_FORMAT,
    level="INFO",
    filter=lambda record: "watchfiles" not in record["message"],
)

# Rotating file
logger.add(
    LOG_FILE,
    format=LOG_FORMAT,
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)


# ── Bridge stdlib → loguru ────────────────────────────
class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logger_opt = logger.opt(depth=6, exception=record.exc_info)
        logger_opt.log(record.levelname, record.getMessage())


logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

logger.complete()
