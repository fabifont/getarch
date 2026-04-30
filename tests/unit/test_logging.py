import logging

from getarch.logging import configure_logging, redact_secret


def test_configure_logging_is_idempotent() -> None:
    configure_logging(level="INFO")
    h1 = logging.getLogger("getarch").handlers
    configure_logging(level="INFO")
    h2 = logging.getLogger("getarch").handlers
    assert len(h1) == len(h2) == 1


def test_configure_logging_respects_level() -> None:
    configure_logging(level="DEBUG")
    assert logging.getLogger("getarch").getEffectiveLevel() == logging.DEBUG


def test_redact_secret_replaces_value() -> None:
    msg = "passwd: hunter2"
    assert redact_secret(msg, "hunter2") == "passwd: ***"


def test_redact_secret_handles_empty_or_none() -> None:
    assert redact_secret("x", "") == "x"
    assert redact_secret("x", None) == "x"
