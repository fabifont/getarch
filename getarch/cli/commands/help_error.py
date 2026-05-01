"""`getarch help error <code>` - print docs for an error code."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.errors import ERROR_CODES


def _docs_root() -> Path:
    """Return ``<repo>/docs/errors`` next to the installed package.

    Falls back to ``$GETARCH_ERROR_DOCS_DIR`` so users running from a
    wheel can ship the markdown stubs alongside the install.
    """
    import os  # noqa: PLC0415

    env = os.environ.get("GETARCH_ERROR_DOCS_DIR")
    if env:
        return Path(env)
    # The package lives at <repo>/getarch/cli/commands/help_error.py;
    # walk three parents to reach <repo>/, then docs/errors.
    return Path(__file__).resolve().parents[3] / "docs" / "errors"


def run(
    code: str = typer.Argument(..., help="Error code, e.g. E102"),
) -> None:
    """Print the docs/errors/<code>.md page for the given code."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(no_color=bool(obj.get("no_color")))
    normalised = code.strip().upper()
    if normalised not in ERROR_CODES:
        console.error(
            f"unknown error code {normalised!r}; known: {', '.join(ERROR_CODES)}",
        )
        raise typer.Exit(code=2)
    docs_path = _docs_root() / f"{normalised}.md"
    if not docs_path.is_file():
        console.error(
            f"docs for {normalised!r} not found at {docs_path}; "
            "the install may be incomplete.",
        )
        raise typer.Exit(code=2)
    sys.stdout.write(docs_path.read_text(encoding="utf-8"))
    if not docs_path.read_text(encoding="utf-8").endswith("\n"):
        sys.stdout.write("\n")
