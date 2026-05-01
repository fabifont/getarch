"""`getarch install CONFIG` - validate, plan, confirm, execute."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from getarch.cli.commands.discover import build_discovery_runner
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
from getarch.execution.state import (
    PipelineState,
    default_state_path,
    fingerprint_plan_text,
)
from getarch.installers.confirmation import require_destructive_confirmation
from getarch.installers.pipeline_builder import build_install_pipeline_steps
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_json, render_text
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.environment import IsoEnvironment
from getarch.system.firmware import EfivarsFirmware
from getarch.system.identity import OsIdentity
from getarch.system.iso import OsReleaseIso
from getarch.system.network import SocketNetwork
from getarch.system.pacman import Pacman
from getarch.system.preflight import EnvironmentReport, preflight_environment


def _discover_disks() -> tuple[Disk, ...]:
    return LsblkBlockDevices(
        runner=build_discovery_runner(no_cache=False),
    ).list_disks()


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
            vendor = IsoEnvironment(
                runner=build_discovery_runner(no_cache=False),
            ).cpu_vendor()
        except OSError:
            vendor = None
        if cfg.microcode.kind == "auto" and vendor is None:
            console.log(
                "[yellow]warning: microcode=auto with skipped preflight and no "
                "cpu_vendor available; no microcode will be installed. Set "
                "microcode.kind explicitly to silence this.[/yellow]",
            )
        return None, vendor
    discovery_runner = build_discovery_runner(no_cache=False)
    real = RealRunner()
    report = preflight_environment(
        cfg,
        LsblkBlockDevices(runner=discovery_runner),
        IsoEnvironment(runner=discovery_runner),
        EfivarsFirmware(),
        Pacman(runner=real),
        OsIdentity(),
        OsReleaseIso(),
        SocketNetwork(),
    )
    return report, report.cpu_vendor


def _resolve_initial_state(
    *,
    mount_root: Path,
    resume: bool,
    dry_run: bool,
    console: GetarchConsole,
    plan_fingerprint: str,
    force_fingerprint: bool,
) -> PipelineState:
    if dry_run:
        return PipelineState(plan_fingerprint=plan_fingerprint)
    state_path = default_state_path(mount_root)
    if not state_path.is_file():
        if resume:
            console.log(
                f"[yellow]--resume given but no state at {state_path}; "
                "starting from scratch[/yellow]",
            )
        return PipelineState(plan_fingerprint=plan_fingerprint)
    if not resume:
        raise PlanError(
            f"existing pipeline state at {state_path}; pass --resume to "
            "continue, or remove the file to start over",
        )
    state = PipelineState.read(state_path)
    if (
        state.plan_fingerprint is not None
        and state.plan_fingerprint != plan_fingerprint
        and not force_fingerprint
    ):
        raise PlanError(
            f"plan fingerprint mismatch (state={state.plan_fingerprint[:12]}, "
            f"current={plan_fingerprint[:12]}); the config or planner has "
            f"changed since the previous run. Pass --force-fingerprint to "
            f"resume against the new plan, or remove {state_path} to start "
            f"over.",
        )
    state.plan_fingerprint = plan_fingerprint
    console.log(
        f"[yellow]resuming after {len(state.completed)} completed steps "
        f"(last error: {state.last_error or 'none'})[/yellow]",
    )
    return state


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
    initial_state: PipelineState,
) -> None:
    exec_ctx = ExecutionContext(
        runner=audit_runner,
        mount_root=mount_root,
        assume_yes=assume_yes,
        force=force,
    )
    steps = build_install_pipeline_steps(
        plan,
        cfg=cfg,
        audit_runner=audit_runner,
        mount_root=mount_root,
        dry_run=dry_run,
        skip_runtime_preflight=skip_runtime_preflight,
    )
    state_path = None if dry_run else default_state_path(mount_root)
    Pipeline(
        steps=tuple(steps),  # type: ignore[arg-type]
        state_path=state_path,
        initial_state=initial_state,
    ).run(exec_ctx)


def _flush_audit_on_failure(
    audit_runner: LoggingRunner,
    *,
    mount_root: Path,
    console: GetarchConsole,
) -> None:
    """Best-effort write of the audit log when the pipeline fails before cleanup.

    The target is still mounted in the failure path, so the log lands on the
    real filesystem. Any error here is swallowed: we are already on the
    failure path, do not mask the original exception.
    """
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
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Skip steps recorded in <mount>/var/log/getarch.state.json from a previous run.",
    ),
    force_fingerprint: bool = typer.Option(
        False,
        "--force-fingerprint",
        help=(
            "With --resume, allow continuing even if the rendered plan no "
            "longer matches the fingerprint stored in the state file. Use "
            "this only when you know the new plan really should reuse the "
            "previous step IDs."
        ),
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
        if cfg.firmware == "container":
            # Container mode skips disk discovery + environment preflight;
            # the caller is responsible for the chroot mount + keyring.
            target = None
            report = None
            cpu_vendor = None
        else:
            disks = _discover_disks()
            report, cpu_vendor = _resolve_environment(
                cfg,
                skip_environment_preflight=skip_environment_preflight,
                console=console,
            )
            target = next(
                (d for d in disks if d.path.as_posix() == cfg.disk.path), None,
            )
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
            existing_filesystems=(
                report.existing_filesystems_seen if report else ()
            ),
        )
        audit_runner = LoggingRunner(inner=_build_runner(dry_run=dry_run))
        plan_blob = render_json(plan)
        plan_fingerprint = fingerprint_plan_text(plan_blob)
        initial_state = _resolve_initial_state(
            mount_root=mount_root,
            resume=resume,
            dry_run=dry_run,
            console=console,
            plan_fingerprint=plan_fingerprint,
            force_fingerprint=force_fingerprint,
        )
        initial_state.plan_blob = plan_blob
        try:
            _execute_pipeline(
                plan,
                cfg=cfg,
                audit_runner=audit_runner,
                mount_root=mount_root,
                assume_yes=assume_yes,
                force=force,
                dry_run=dry_run,
                skip_runtime_preflight=skip_runtime_preflight,
                initial_state=initial_state,
            )
        except GetarchError:
            if not dry_run:
                _flush_audit_on_failure(
                    audit_runner, mount_root=mount_root, console=console,
                )
            raise
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None
    if dry_run:
        console.log("[yellow]dry-run completed[/yellow]")
    else:
        console.log("[green]install completed[/green]")
