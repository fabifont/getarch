"""`getarch microcode CONFIG` - print the resolved MicrocodeKind for a host."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.domain.kernel import MicrocodeKind
from getarch.errors import GetarchError
from getarch.execution.real_runner import RealRunner
from getarch.system.environment import IsoEnvironment


def _resolve_microcode(cfg_kind: str, cpu_vendor: str | None) -> MicrocodeKind:
    if cfg_kind == "intel":
        return MicrocodeKind.INTEL
    if cfg_kind == "amd":
        return MicrocodeKind.AMD
    if cfg_kind == "none":
        return MicrocodeKind.NONE
    return MicrocodeKind.from_cpu_vendor(cpu_vendor)


def run(
    config: Path = typer.Argument(..., exists=True),
) -> None:
    """Resolve microcode for ``config`` against this host's CPU vendor."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg = load_config(config)
        validate_semantics(cfg)
        try:
            cpu_vendor = IsoEnvironment(runner=RealRunner()).cpu_vendor()
        except OSError:
            cpu_vendor = None
        resolved = _resolve_microcode(cfg.microcode.kind, cpu_vendor)
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None

    payload = {
        "configured": cfg.microcode.kind,
        "cpu_vendor": cpu_vendor,
        "resolved": resolved.value,
        "package": resolved.package_name,
    }
    if obj.get("json_mode"):
        console.log(payload)
    else:
        pkg = resolved.package_name or "(none)"
        console.log(
            f"configured={cfg.microcode.kind} "
            f"cpu_vendor={cpu_vendor!r} "
            f"resolved={resolved.value} package={pkg}",
        )
