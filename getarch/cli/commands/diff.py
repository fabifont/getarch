"""`getarch diff CONFIG_A CONFIG_B` - render a unified diff of two plans."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import GetarchError
from getarch.planning.planner import Planner


def _render_steps(planner_output: object) -> list[str]:
    # Late import keeps the cli boot path lean.
    from getarch.domain.plan import InstallPlan

    assert isinstance(planner_output, InstallPlan)
    lines: list[str] = []
    for step in planner_output.steps:
        flag = " (destructive)" if step.destructive else ""
        lines.append(f"# {step.id}{flag}: {step.title}")
        for cmd in step.commands:
            chroot_marker = "[chroot] " if cmd.chroot else ""
            lines.append(f"  {chroot_marker}{cmd.describe()}")
    return lines


def run(
    config_a: Path = typer.Argument(..., exists=True, help="Baseline config."),
    config_b: Path = typer.Argument(..., exists=True, help="Comparison config."),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
) -> None:
    """Render a unified diff between the plans built from two configs.

    The disk discovery is skipped — both configs are validated against
    pydantic + the semantic checks, then a stub Disk is fed to the
    planner so the diff covers planner output without touching the live
    system.
    """
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg_a = load_config(config_a)
        validate_semantics(cfg_a)
        cfg_b = load_config(config_b)
        validate_semantics(cfg_b)
        # Stub disk shared across both renders; the planner only reads
        # `disk.path` for the partitioning step which is itself a string
        # in the rendered diff.
        disk = Disk(path=DiskPath(Path(cfg_a.disk.path)), size_bytes=2**40)
        plan_a = Planner().build(cfg=cfg_a, disk=disk, mount_root=mount_root)
        disk_b = Disk(path=DiskPath(Path(cfg_b.disk.path)), size_bytes=2**40)
        plan_b = Planner().build(cfg=cfg_b, disk=disk_b, mount_root=mount_root)
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None

    lines_a = _render_steps(plan_a)
    lines_b = _render_steps(plan_b)
    diff = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=str(config_a),
        tofile=str(config_b),
        lineterm="",
    )
    rendered = "\n".join(diff)
    if not rendered:
        console.log("[green]plans are identical[/green]")
        return
    sys.stdout.write(rendered + "\n")
