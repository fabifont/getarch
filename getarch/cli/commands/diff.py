"""`getarch diff` - render a unified diff of two plans.

Two modes:

* ``getarch diff CONFIG_A CONFIG_B`` — diff between two configs.
* ``getarch diff CONFIG --against-installed`` — diff between ``CONFIG`` and
  the plan recorded in ``<mount>/var/log/getarch.state.json`` from the
  previous install.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Any, cast

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk, DiskPath
from getarch.domain.plan import InstallPlan, PlannedStep, StepPhase
from getarch.errors import GetarchError, PlanError
from getarch.execution.command import Command
from getarch.execution.state import PipelineState, default_state_path
from getarch.planning.planner import Planner


def _render_steps(plan: InstallPlan) -> list[str]:
    lines: list[str] = []
    for step in plan.steps:
        flag = " (destructive)" if step.destructive else ""
        lines.append(f"# {step.id}{flag}: {step.title}")
        for cmd in step.commands:
            chroot_marker = "[chroot] " if cmd.chroot else ""
            lines.append(f"  {chroot_marker}{cmd.describe()}")
    return lines


def _plan_from_state_blob(blob: str) -> InstallPlan:
    payload = cast("dict[str, Any]", json.loads(blob))
    raw_steps = cast("list[dict[str, Any]]", payload.get("steps", []))
    steps: list[PlannedStep] = []
    for raw in raw_steps:
        commands_raw = cast("list[dict[str, Any]]", raw.get("commands", []))
        commands: list[Command] = []
        for c in commands_raw:
            argv_raw = cast("list[str]", c.get("argv", []))
            argv = tuple(str(item) for item in argv_raw)
            description_raw = c.get("description")
            commands.append(
                Command(
                    argv=argv,
                    chroot=bool(c.get("chroot", False)),
                    sensitive=bool(c.get("sensitive", False)),
                    description=str(description_raw) if description_raw else None,
                ),
            )
        steps.append(
            PlannedStep(
                id=str(raw["id"]),
                title=str(raw["title"]),
                phase=StepPhase(str(raw["phase"])),
                commands=tuple(commands),
                destructive=bool(raw.get("destructive", False)),
                description=str(raw.get("description", "")),
            ),
        )
    return InstallPlan(version=str(payload.get("version", "1")), steps=tuple(steps))


def _diff_lines(
    label_a: str, lines_a: list[str], label_b: str, lines_b: list[str],
) -> str:
    return "\n".join(
        difflib.unified_diff(
            lines_a, lines_b, fromfile=label_a, tofile=label_b, lineterm="",
        ),
    )


def run(
    config: Path = typer.Argument(..., exists=True, help="Config to compare."),
    config_b: Path | None = typer.Argument(
        None,
        exists=True,
        help="Optional second config; required without --against-installed.",
    ),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
    against_installed: bool = typer.Option(
        False,
        "--against-installed",
        help=(
            "Compare against the plan persisted at "
            "<mount>/var/log/getarch.state.json from the previous install."
        ),
    ),
) -> None:
    """Render a unified diff between two plans."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg_a = load_config(config)
        validate_semantics(cfg_a)
        disk_a = Disk(path=DiskPath(Path(cfg_a.disk.path)), size_bytes=2**40)
        plan_a = Planner().build(cfg=cfg_a, disk=disk_a, mount_root=mount_root)
        if against_installed:
            if config_b is not None:
                raise PlanError(
                    "--against-installed cannot be combined with a second "
                    "config argument",
                )
            state_path = default_state_path(mount_root)
            if not state_path.is_file():
                console.log(
                    f"[yellow]no previous install state at {state_path}; "
                    "nothing to diff against[/yellow]",
                )
                return
            state = PipelineState.read(state_path)
            if not state.plan_blob:
                console.log(
                    f"[yellow]state at {state_path} has no plan_blob "
                    "(probably written by an older getarch); nothing to "
                    "diff against[/yellow]",
                )
                return
            plan_b = _plan_from_state_blob(state.plan_blob)
            label_b = str(state_path)
        else:
            if config_b is None:
                raise PlanError(
                    "two CONFIG paths required when --against-installed is "
                    "not set",
                )
            cfg_b = load_config(config_b)
            validate_semantics(cfg_b)
            disk_b = Disk(path=DiskPath(Path(cfg_b.disk.path)), size_bytes=2**40)
            plan_b = Planner().build(cfg=cfg_b, disk=disk_b, mount_root=mount_root)
            label_b = str(config_b)
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None

    rendered = _diff_lines(
        str(config), _render_steps(plan_a), label_b, _render_steps(plan_b),
    )
    if not rendered:
        console.log("[green]plans are identical[/green]")
        return
    sys.stdout.write(rendered + "\n")
