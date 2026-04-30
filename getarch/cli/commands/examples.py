"""`getarch examples [NAME]` - list or print example configs."""

from __future__ import annotations

import sys

import typer

from getarch.config.examples import EXAMPLES, render_example


def run(name: str | None = typer.Argument(None)) -> None:
    if name is None:
        sys.stdout.write("\n".join(sorted(EXAMPLES)) + "\n")
        return
    if name not in EXAMPLES:
        raise typer.Exit(code=2)
    sys.stdout.write(render_example(name) + "\n")
