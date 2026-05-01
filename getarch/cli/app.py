"""Typer CLI entry point."""

from __future__ import annotations

import click
import typer

from getarch.cli.commands import (
    diff as diff_cmd,
)
from getarch.cli.commands import (
    discover as discover_cmd,
)
from getarch.cli.commands import (
    examples as examples_cmd,
)
from getarch.cli.commands import (
    install as install_cmd,
)
from getarch.cli.commands import (
    microcode as microcode_cmd,
)
from getarch.cli.commands import (
    plan as plan_cmd,
)
from getarch.cli.commands import (
    schema as schema_cmd,
)
from getarch.cli.commands import (
    tui as tui_cmd,
)
from getarch.cli.commands import (
    validate as validate_cmd,
)
from getarch.cli.commands import (
    verify as verify_cmd,
)
from getarch.cli.commands import (
    version as version_cmd,
)
from getarch.logging import LogLevel, configure_logging

app = typer.Typer(
    name="getarch",
    help="Declarative Arch Linux base-system installer.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _main_callback(  # type: ignore[reportUnusedFunction]  # registered via decorator
    log_level: str = typer.Option("INFO", "--log-level"),
    no_color: bool = typer.Option(False, "--no-color"),
    json_mode: bool = typer.Option(False, "--json"),
    verbose: bool = typer.Option(False, "--verbose"),
    debug: bool = typer.Option(False, "--debug"),
) -> None:
    if debug:
        configure_logging(level="DEBUG")
    elif verbose:
        configure_logging(level="INFO")
    else:
        # Trust the CLI input; only documented log levels are accepted by Typer
        # callers. We still validate against the Literal values defensively.
        valid: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level: LogLevel = log_level if log_level in valid else "INFO"  # type: ignore[assignment]
        configure_logging(level=level)
    ctx = click.get_current_context()
    ctx.obj = {
        "log_level": log_level,
        "no_color": no_color,
        "json_mode": json_mode,
        "verbose": verbose,
        "debug": debug,
    }


app.command("validate")(validate_cmd.run)
app.command("plan")(plan_cmd.run)
app.command("install")(install_cmd.run)
app.command("diff")(diff_cmd.run)
app.command("schema")(schema_cmd.run)
app.command("examples")(examples_cmd.run)
app.command("discover")(discover_cmd.run)
app.command("tui")(tui_cmd.run)
app.command("verify")(verify_cmd.run)
app.command("microcode")(microcode_cmd.run)
app.command("version")(version_cmd.run)


def main() -> None:
    app()
