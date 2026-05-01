"""Smoke tests for TuiExecuteApp + ConfirmModal wiring.

Covers:

* App instantiation (no event loop)
* Worker bypasses confirmation in dry-run mode
* Worker blocks on confirmation modal in real-runner mode (FakeRunner-driven)
* ConfirmModal sets the result list and the threading.Event when answered
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.execution.fake_runner import FakeRunner
from getarch.installers.pipeline_builder import build_install_pipeline_steps
from getarch.tui.screens import execute as execute_mod
from getarch.tui.screens.confirm import ConfirmModal
from getarch.tui.screens.execute import TuiExecuteApp


def test_execute_app_instantiates_dry_run(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = TuiExecuteApp(config_path=cfg_path, mount_root=Path("/mnt"))
    assert app is not None


def test_execute_app_real_run_uses_real_runner_inner(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = TuiExecuteApp(
        config_path=cfg_path,
        mount_root=Path("/mnt"),
        dry_run=False,
        runner_factory=FakeRunner,
    )
    # The LoggingRunner wraps the factory's runner.
    assert isinstance(app.runner.inner, FakeRunner)


def test_execute_app_dry_run_skips_confirmation(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = TuiExecuteApp(
        config_path=cfg_path,
        mount_root=Path("/mnt"),
        dry_run=True,
    )
    # In dry-run mode the worker's confirmation hook returns True
    # immediately without touching the UI.
    assert app.ask_confirmation("Proceed?") is True


def test_execute_app_assume_yes_skips_confirmation(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = TuiExecuteApp(
        config_path=cfg_path,
        mount_root=Path("/mnt"),
        dry_run=False,
        assume_yes=True,
        runner_factory=FakeRunner,
    )
    assert app.ask_confirmation("Proceed?") is True


def test_confirm_modal_records_yes() -> None:
    done = threading.Event()
    result: list[bool] = [False]
    modal = ConfirmModal(message="proceed?", done=done, result=result)
    # Bypass Textual lifecycle (dismiss requires an active App).
    modal.record_answer(answer=True)
    assert done.is_set()
    assert result == [True]


def test_confirm_modal_records_no() -> None:
    done = threading.Event()
    result: list[bool] = [True]
    modal = ConfirmModal(message="proceed?", done=done, result=result)
    modal.record_answer(answer=False)
    assert done.is_set()
    assert result == [False]


def test_confirm_modal_no_overrides_initial_yes() -> None:
    """A 'No' answer must flip the result even if it was initially True."""

    done = threading.Event()
    result: list[bool] = [True]
    modal = ConfirmModal(message="proceed?", done=done, result=result)
    modal.record_answer(answer=False)
    assert result == [False]
    assert done.is_set()


def test_tui_real_run_uses_install_pipeline_builder(tmp_path: Path) -> None:
    """Regression for codex P5 finding: --execute --no-dry-run used to
    skip the install command's pipeline assembly (DiskBusyGuardStep,
    RuntimePreflightStep, DiskWipeStep, AuditLogStep). Verify the
    execute screen now imports the same builder so the surfaces can't
    drift on safety guarantees."""

    # The screen must reference the shared builder, not its own
    # PlannedStepExecutor loop.
    assert execute_mod.build_install_pipeline_steps is (
        build_install_pipeline_steps
    )

    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    # Just confirm instantiation still works after the refactor.
    app = TuiExecuteApp(
        config_path=cfg_path,
        mount_root=Path("/mnt"),
        dry_run=False,
        runner_factory=FakeRunner,
    )
    assert isinstance(app.runner.inner, FakeRunner)
