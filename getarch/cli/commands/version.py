"""`getarch version` - prints package version."""

from __future__ import annotations

import click

from getarch import __version__
from getarch.cli.output import GetarchConsole


def run() -> None:
    """Print the getarch version."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(
        json_mode=bool(obj.get("json_mode")),
        no_color=bool(obj.get("no_color")),
    )
    if obj.get("json_mode"):
        console.log({"version": __version__})
    else:
        console.log(__version__)
