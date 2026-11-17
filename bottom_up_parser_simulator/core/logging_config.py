"""Logging configuration for the bottom-up parser simulator application."""

import logging
import logging.handlers
import sys
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "application.log"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_LEVEL = logging.DEBUG


def setup_logging() -> None:
    """Configure application-wide logging to file and console.

    Creates the logs directory if it does not exist and installs:
    * a rotating file handler writing to logs/application.log
    * a console handler writing to stderr

    The root logger is configured at DEBUG level so individual loggers
    can filter themselves.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if root_logger.handlers:
        return

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    return logging.getLogger(name)
