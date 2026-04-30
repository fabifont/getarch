"""Logging configuration. Logging is never auto-configured at import time."""

from __future__ import annotations

import logging
from typing import Final, Literal

from rich.logging import RichHandler

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_LOGGER_NAME: Final = "getarch"
_CONFIGURED: Final = "_getarch_configured"


def configure_logging(level: LogLevel = "INFO", *, show_path: bool = False) -> None:
    """Install a single :class:`RichHandler` on the ``getarch`` logger; idempotent."""
    logger = logging.getLogger(_LOGGER_NAME)
    if getattr(logger, _CONFIGURED, False):
        logger.setLevel(level)
        return
    logger.setLevel(level)
    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=show_path,
        markup=False,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    logger._getarch_configured = True  # type: ignore[attr-defined]


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def redact_secret(message: str, secret: str | None) -> str:
    """Replace ``secret`` with ``***`` in ``message``. No-op for empty/None."""
    if not secret:
        return message
    return message.replace(secret, "***")
