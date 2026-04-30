"""`getarch validate CONFIG`."""

from __future__ import annotations

from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.errors import GetarchError


def run(
    config: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Validate a getarch config (syntactic + semantic)."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    try:
        cfg = load_config(config)
        validate_semantics(cfg)
    except GetarchError as exc:
        console.error(str(exc))
        raise typer.Exit(code=2) from None
    if obj.get("json_mode"):
        console.log({"status": "ok", "version": cfg.version})
    else:
        console.log("[green]config is valid[/green]")
