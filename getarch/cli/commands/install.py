"""`getarch install CONFIG` - validate, plan, confirm, execute."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk
from getarch.errors import GetarchError, PlanError
from getarch.execution.context import ExecutionContext
from getarch.execution.dry_runner import DryRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.real_runner import RealRunner
from getarch.execution.runner import CommandRunner
from getarch.installers.base import PlannedStepExecutor
from getarch.installers.confirmation import require_destructive_confirmation
from getarch.installers.preflight import RuntimePreflightStep
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_text
from getarch.system.block_devices import LsblkBlockDevices


def _discover_disks() -> tuple[Disk, ...]:
    return LsblkBlockDevices(runner=RealRunner()).list_disks()


def _build_runner(*, dry_run: bool) -> CommandRunner:
    return DryRunner() if dry_run else RealRunner()


def run(
    config: Path = typer.Argument(..., exists=True),
    dry_run: bool = typer.Option(False, "--dry-run"),
    assume_yes: bool = typer.Option(False, "--yes", "-y"),
    force: bool = typer.Option(False, "--force"),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
    skip_runtime_preflight: bool = typer.Option(False, "--skip-runtime-preflight"),
) -> None:
    """Run the full install pipeline."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg = load_config(config)
        validate_semantics(cfg)
        disks = _discover_disks()
        target = next((d for d in disks if d.path.as_posix() == cfg.disk.path), None)
        if target is None:
            raise PlanError(f"target disk {cfg.disk.path} not present")
        plan = Planner().build(cfg=cfg, disk=target, mount_root=mount_root)
        console.log(render_text(plan))
        require_destructive_confirmation(
            plan,
            assume_yes=assume_yes,
            force=force,
            prompt=console.confirm,
        )
        runner = _build_runner(dry_run=dry_run)
        exec_ctx = ExecutionContext(
            runner=runner,
            mount_root=mount_root,
            assume_yes=assume_yes,
            force=force,
        )
        steps: list[object] = []
        if not skip_runtime_preflight and not dry_run:
            steps.append(RuntimePreflightStep())
        steps.extend(PlannedStepExecutor(planned=s) for s in plan.steps)
        Pipeline(steps=tuple(steps)).run(exec_ctx)  # type: ignore[arg-type]
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None
    if dry_run:
        console.log("[yellow]dry-run completed[/yellow]")
    else:
        console.log("[green]install completed[/green]")
