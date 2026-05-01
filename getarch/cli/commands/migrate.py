"""`getarch migrate CONFIG --to N` - upgrade a config file to a newer schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.config.loader import parse_text
from getarch.config.migrations import migrate
from getarch.errors import GetarchError, SyntacticConfigError


def run(
    config: Path = typer.Argument(..., exists=True),
    to_version: int = typer.Option(2, "--to", help="Target schema version."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write migrated config to this path (defaults to stdout).",
    ),
) -> None:
    """Migrate a config file to a newer schema version."""
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    console = GetarchConsole(no_color=bool(obj.get("no_color")))
    try:
        text = config.read_text(encoding="utf-8")
        raw = parse_text(config, text)
        if not isinstance(raw, dict):
            raise SyntacticConfigError("config root must be an object")
        # Cast happens implicitly via the dict isinstance gate above.
        migrated = migrate(raw, to_version=to_version)  # type: ignore[arg-type]
        rendered = json.dumps(migrated, indent=2, sort_keys=False) + "\n"
    except GetarchError as exc:
        console.render_exception(exc)
        raise typer.Exit(code=2) from None
    except OSError as exc:
        console.error(f"could not read {config}: {exc}")
        raise typer.Exit(code=2) from None
    if output is None:
        sys.stdout.write(rendered)
        return
    try:
        output.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        console.error(f"could not write {output}: {exc}")
        raise typer.Exit(code=2) from None
    console.log(f"[green]migrated to v{to_version} → {output}[/green]")
