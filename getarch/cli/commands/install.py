"""`getarch install CONFIG` - validate, plan, confirm, execute."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk
from getarch.domain.plan import InstallPlan
from getarch.errors import GetarchError, PlanError
from getarch.execution.context import ExecutionContext
from getarch.execution.dry_runner import DryRunner
from getarch.execution.logging_runner import LoggingRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.real_runner import RealRunner
from getarch.execution.runner import CommandRunner
from getarch.installers.base import PlannedStepExecutor
from getarch.installers.confirmation import require_destructive_confirmation
from getarch.installers.preflight import DiskBusyGuardStep, RuntimePreflightStep
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_text
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.environment import IsoEnvironment
from getarch.system.firmware import EfivarsFirmware
from getarch.system.identity import OsIdentity
from getarch.system.iso import OsReleaseIso
from getarch.system.network import SocketNetwork
from getarch.system.pacman import Pacman
from getarch.system.preflight import EnvironmentReport, preflight_environment


def _discover_disks() -> tuple[Disk, ...]:
    return LsblkBlockDevices(runner=RealRunner()).list_disks()


def _build_runner(*, dry_run: bool) -> CommandRunner:
    return DryRunner() if dry_run else RealRunner()


def _resolve_environment(
    cfg: Config,
    *,
    skip_environment_preflight: bool,
    console: GetarchConsole,
) -> tuple[EnvironmentReport | None, str | None]:
    if skip_environment_preflight:
        console.log(
            "[yellow]skipping environment preflight "
            "(--skip-environment-preflight)[/yellow]",
        )
        try:
            vendor = IsoEnvironment(runner=RealRunner()).cpu_vendor()
        except OSError:
            vendor = None
        if cfg.microcode.kind == "auto" and vendor is None:
            console.log(
                "[yellow]warning: microcode=auto with skipped preflight and no "
                "cpu_vendor available; no microcode will be installed. Set "
                "microcode.kind explicitly to silence this.[/yellow]",
            )
        return None, vendor
    real = RealRunner()
    report = preflight_environment(
        cfg,
        LsblkBlockDevices(runner=real),
        IsoEnvironment(runner=real),
        EfivarsFirmware(),
        Pacman(runner=real),
        OsIdentity(),
        OsReleaseIso(),
        SocketNetwork(),
    )
    return report, report.cpu_vendor


def _execute_pipeline(
    plan: InstallPlan,
    *,
    cfg: Config,
    audit_runner: LoggingRunner,
    mount_root: Path,
    assume_yes: bool,
    force: bool,
    dry_run: bool,
    skip_runtime_preflight: bool,
) -> None:
    exec_ctx = ExecutionContext(
        runner=audit_runner,
        mount_root=mount_root,
        assume_yes=assume_yes,
        force=force,
    )
    steps: list[object] = []
    if not dry_run:
        steps.append(
            DiskBusyGuardStep(
                block_devices=LsblkBlockDevices(runner=RealRunner()),
                target_disk_path=cfg.disk.path,
            ),
        )
    if not skip_runtime_preflight and not dry_run:
        steps.append(RuntimePreflightStep())
    steps.extend(PlannedStepExecutor(planned=s) for s in plan.steps)
    Pipeline(steps=tuple(steps)).run(exec_ctx)  # type: ignore[arg-type]


def _write_audit_log(
    audit_runner: LoggingRunner,
    *,
    mount_root: Path,
    console: GetarchConsole,
) -> None:
    log_path = mount_root / "var/log/getarch.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(audit_runner.render(), encoding="utf-8")
    except OSError as exc:
        console.log(
            f"[yellow]warning: could not write audit log to "
            f"{log_path}: {exc}[/yellow]",
        )


def run(
    config: Path = typer.Argument(..., exists=True),
    dry_run: bool = typer.Option(False, "--dry-run"),
    assume_yes: bool = typer.Option(False, "--yes", "-y"),
    force: bool = typer.Option(False, "--force"),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
    skip_runtime_preflight: bool = typer.Option(False, "--skip-runtime-preflight"),
    skip_environment_preflight: bool = typer.Option(
        False,
        "--skip-environment-preflight",
    ),
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
        report, cpu_vendor = _resolve_environment(
            cfg,
            skip_environment_preflight=skip_environment_preflight,
            console=console,
        )
        target = next((d for d in disks if d.path.as_posix() == cfg.disk.path), None)
        if target is None:
            raise PlanError(f"target disk {cfg.disk.path} not present")
        plan = Planner().build(
            cfg=cfg,
            disk=target,
            mount_root=mount_root,
            cpu_vendor=cpu_vendor,
        )
        console.log(render_text(plan))
        require_destructive_confirmation(
            plan,
            assume_yes=assume_yes,
            force=force,
            prompt=console.confirm,
            mounts_summary=report.mountpoints_seen if report else (),
        )
        audit_runner = LoggingRunner(inner=_build_runner(dry_run=dry_run))
        _execute_pipeline(
            plan,
            cfg=cfg,
            audit_runner=audit_runner,
            mount_root=mount_root,
            assume_yes=assume_yes,
            force=force,
            dry_run=dry_run,
            skip_runtime_preflight=skip_runtime_preflight,
        )
        if not dry_run:
            _write_audit_log(audit_runner, mount_root=mount_root, console=console)
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None
    if dry_run:
        console.log("[yellow]dry-run completed[/yellow]")
    else:
        console.log("[green]install completed[/green]")
