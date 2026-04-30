"""`getarch plan CONFIG` - render the install plan, no execution."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk
from getarch.errors import GetarchError, PlanError
from getarch.execution.real_runner import RealRunner
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_json, render_text
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.environment import IsoEnvironment


def _discover_disks() -> tuple[Disk, ...]:
    return LsblkBlockDevices(runner=RealRunner()).list_disks()


def _discover_cpu_vendor() -> str | None:
    try:
        return IsoEnvironment(runner=RealRunner()).cpu_vendor()
    except OSError:
        return None


def run(
    config: Path = typer.Argument(..., exists=True),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
) -> None:
    """Render the install plan without executing anything."""
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
        plan = Planner().build(
            cfg=cfg,
            disk=target,
            mount_root=mount_root,
            cpu_vendor=_discover_cpu_vendor(),
        )
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None

    if obj.get("json_mode"):
        sys.stdout.write(render_json(plan) + "\n")
    else:
        console.log(render_text(plan))
