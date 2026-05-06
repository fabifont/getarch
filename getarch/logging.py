"""Logging configuration.

Single :func:`configure_logging` entry point installs a Rich-formatted
handler on the ``getarch`` logger. Optional ``sink`` adds a second
handler (syslog or journald) so per-step logs can stream to the host
logging infrastructure on long-running installs.

Logging is never auto-configured at import time.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import SysLogHandler
from typing import Final, Literal, override

from rich.logging import RichHandler

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]

_LOGGER_NAME: Final = "getarch"
_CONFIGURED: Final = "_getarch_configured"
_DEFAULT_SYSLOG_ADDRESS: Final[str] = "/dev/log"


class JsonFormatter(logging.Formatter):
    """Render every record as a single-line JSON object."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _build_syslog_handler(spec: str) -> logging.Handler:
    """Construct a :class:`SysLogHandler` from ``syslog`` or ``syslog://host:port``."""
    if spec == "syslog":
        return SysLogHandler(address=_DEFAULT_SYSLOG_ADDRESS)
    if spec.startswith("syslog://"):
        rest = spec[len("syslog://") :]
        host, _, port = rest.partition(":")
        return SysLogHandler(address=(host, int(port) if port else 514))
    raise ValueError(f"unsupported syslog sink {spec!r}")


def _build_journald_handler() -> logging.Handler:
    """Construct a journald handler if ``systemd.journal`` is importable.

    Imported lazily because ``systemd`` is an optional dependency: the
    install must remain usable on hosts that don't ship python-systemd
    (e.g. minimal containers).
    """
    # type: ignore covers both the missing module (CI without systemd)
    # and the missing stubs; the call site below is pyright-ignored so
    # the unknown-return type from the optional dep doesn't bleed into
    # typed callers. Lazy import keeps startup fast on hosts without
    # python-systemd.
    try:
        from systemd.journal import JournalHandler  # type: ignore[import-not-found,import-untyped] # noqa: I001,PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "journald sink requires `python-systemd` (extras_require: systemd)",
        ) from exc
    return JournalHandler(SYSLOG_IDENTIFIER="getarch")  # type: ignore[no-any-return,call-arg]  # pyright: ignore[reportUnknownVariableType,reportCallIssue,reportReturnType]


def configure_logging(
    level: LogLevel = "INFO",
    *,
    show_path: bool = False,
    sink: str = "console",
    fmt: LogFormat = "text",
) -> None:
    """Install a single :class:`RichHandler` on the ``getarch`` logger.

    When ``sink`` is non-default, a second handler is added that
    streams the same records to syslog or journald. ``fmt='json'``
    swaps the formatter on the *secondary* handler so the syslog/
    journald destination receives parseable JSON; the human-facing
    Rich handler always uses the friendly format.

    Idempotent — calling twice with the same arguments only updates
    the level.
    """
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
    extra: logging.Handler | None = None
    if sink != "console":
        if sink == "journald":
            extra = _build_journald_handler()
        elif sink == "syslog" or sink.startswith("syslog://"):
            extra = _build_syslog_handler(sink)
        else:
            raise ValueError(f"unsupported log sink {sink!r}")
    if extra is not None:
        if fmt == "json":
            extra.setFormatter(JsonFormatter())
        else:
            extra.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s: %(message)s",
                ),
            )
        logger.addHandler(extra)
    logger.propagate = False
    logger._getarch_configured = True  # type: ignore[attr-defined]


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def redact_secret(message: str, secret: str | None) -> str:
    """Replace ``secret`` with ``***`` in ``message``. No-op for empty/None."""
    if not secret:
        return message
    return message.replace(secret, "***")
