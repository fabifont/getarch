"""Stable error codes + per-code docs stubs + CLI rendering tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from getarch.cli.app import app
from getarch.errors import (
    ERROR_CODES,
    CommandFailedError,
    ConfigError,
    DiscoveryError,
    EnvironmentError,
    GetarchError,
    PlanError,
    SemanticConfigError,
    SyntacticConfigError,
)


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "errors"


@pytest.mark.parametrize("code", ERROR_CODES)
def test_every_code_has_a_docs_stub(code: str) -> None:
    path = _docs_root() / f"{code}.md"
    assert path.is_file(), f"missing docs/errors/{code}.md"
    body = path.read_text(encoding="utf-8")
    assert code in body, f"docs/errors/{code}.md must mention the code itself"


def test_subclasses_have_distinct_codes() -> None:
    classes: list[type[GetarchError]] = [
        GetarchError,
        ConfigError,
        SyntacticConfigError,
        SemanticConfigError,
        EnvironmentError,
        DiscoveryError,
        PlanError,
        CommandFailedError,
    ]
    codes = {c.code for c in classes}
    assert len(codes) == len(classes), "every error class needs a unique code"


def test_get_arch_error_carries_optional_hint() -> None:
    exc = SemanticConfigError("bad", hint="set encryption.kind='luks2'")
    assert exc.hint == "set encryption.kind='luks2'"
    assert exc.code == "E102"
    assert "bad" in str(exc)


def test_command_failed_error_keeps_existing_shape() -> None:
    exc = CommandFailedError(
        argv=("pacstrap", "/mnt"),
        returncode=1,
        stderr="oops",
    )
    assert exc.code == "E400"
    assert exc.argv == ("pacstrap", "/mnt")
    assert exc.returncode == 1
    assert "pacstrap /mnt" in str(exc)


def test_help_error_command_prints_docs(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["help", "error", "E102"])
    assert result.exit_code == 0
    assert "E102" in result.output
    del tmp_path


def test_help_error_command_normalises_lowercase_code() -> None:
    result = CliRunner().invoke(app, ["help", "error", "e102"])
    assert result.exit_code == 0
    assert "E102" in result.output


def test_help_error_command_rejects_unknown_code() -> None:
    result = CliRunner().invoke(app, ["help", "error", "E999"])
    assert result.exit_code != 0
    assert "unknown error code" in result.output.lower()
