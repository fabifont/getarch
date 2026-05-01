"""`getarch verify CONFIG` - re-run preflight without building or executing.

Use this to confirm a config still passes every preflight check on the
current host without bothering to render the plan. Exits 0 on full pass,
2 on any preflight failure (matches the install command's exit codes).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.errors import GetarchError
from getarch.execution.real_runner import RealRunner
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.environment import IsoEnvironment
from getarch.system.firmware import EfivarsFirmware
from getarch.system.identity import OsIdentity
from getarch.system.iso import OsReleaseIso
from getarch.system.network import SocketNetwork
from getarch.system.pacman import Pacman
from getarch.system.preflight import preflight_environment


def run(
    config: Path = typer.Argument(..., exists=True),
) -> None:
    """Re-run preflight checks against ``config`` and report the result."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg = load_config(config)
        validate_semantics(cfg)
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
    except GetarchError as exc:
        console.render_exception(exc)
        raise typer.Exit(code=2) from None

    if obj.get("json_mode"):
        console.log(asdict(report))
    else:
        console.log("[green]preflight OK[/green]")
        console.log(f"  is_uefi={report.is_uefi} is_root={report.is_root}")
        console.log(
            f"  is_arch_iso={report.is_arch_iso} "
            f"internet_reachable={report.internet_reachable} "
            f"keyring_initialized={report.keyring_initialized}",
        )
        console.log(f"  cpu_vendor={report.cpu_vendor!r}")
        console.log(f"  disks_found={sorted(report.disks_found)}")
        if report.mountpoints_seen:
            console.log(f"  mountpoints_seen={list(report.mountpoints_seen)}")
