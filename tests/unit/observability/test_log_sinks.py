"""configure_logging sink + format tests."""

from __future__ import annotations

import json
import logging

import pytest

from getarch.logging import JsonFormatter, configure_logging


def _reset(logger: logging.Logger) -> None:
    """Drop the configured-once flag + handlers so each test starts clean."""
    if hasattr(logger, "_getarch_configured"):
        delattr(logger, "_getarch_configured")
    import contextlib  # noqa: PLC0415

    for h in list(logger.handlers):
        with contextlib.suppress(Exception):
            h.close()
        logger.removeHandler(h)


def test_console_sink_only_installs_rich_handler() -> None:
    logger = logging.getLogger("getarch")
    _reset(logger)
    configure_logging(level="INFO", sink="console")
    # exactly one handler
    assert len(logger.handlers) == 1


def test_syslog_sink_installs_second_handler() -> None:
    pytest.importorskip("logging.handlers")
    logger = logging.getLogger("getarch")
    _reset(logger)
    # The /dev/log socket may not exist in the test container; SysLogHandler
    # construction tolerates a missing path on first message attempt only.
    try:
        configure_logging(level="INFO", sink="syslog")
    except OSError:
        pytest.skip("/dev/log unavailable in this environment")
    assert len(logger.handlers) == 2


def test_unsupported_sink_raises() -> None:
    logger = logging.getLogger("getarch")
    _reset(logger)
    with pytest.raises(ValueError, match="unsupported log sink"):
        configure_logging(level="INFO", sink="bogus")


def test_journald_sink_falls_through_to_runtime_error_when_no_systemd() -> None:
    logger = logging.getLogger("getarch")
    _reset(logger)
    # The CI image may or may not have python-systemd. Either path is
    # acceptable: missing dep surfaces a "python-systemd"-mentioning
    # RuntimeError, present dep installs a second handler.
    try:
        importlib_can_import_systemd = True
        try:
            __import__("systemd.journal")
        except ImportError:
            importlib_can_import_systemd = False

        if importlib_can_import_systemd:
            configure_logging(level="INFO", sink="journald")
            assert len(logger.handlers) == 2
        else:
            with pytest.raises(RuntimeError, match="python-systemd"):
                configure_logging(level="INFO", sink="journald")
    finally:
        _reset(logger)


def test_json_formatter_emits_required_fields() -> None:
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="getarch.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "getarch.test"
    assert parsed["message"] == "hello world"
    assert "ts" in parsed


def test_configure_logging_is_idempotent() -> None:
    logger = logging.getLogger("getarch")
    _reset(logger)
    configure_logging(level="INFO")
    configure_logging(level="DEBUG")
    # No second handler installed — only level was bumped.
    assert len(logger.handlers) == 1
    assert logger.level == logging.DEBUG
