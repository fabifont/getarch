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
    help_error as help_error_cmd,
)
from getarch.cli.commands import (
    install as install_cmd,
)
from getarch.cli.commands import (
    microcode as microcode_cmd,
)
from getarch.cli.commands import (
    migrate as migrate_cmd,
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
    log_sink: str = typer.Option(
        "console",
        "--log-sink",
        help=(
            "Where logs are streamed in addition to the console. "
            "Accepts 'console', 'syslog', 'syslog://host:port', or 'journald' "
            "(requires python-systemd)."
        ),
    ),
    log_format: str = typer.Option(
        "text",
        "--log-format",
        help="Format for non-console sinks: 'text' or 'json'.",
    ),
) -> None:
    valid_levels: set[str] = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    valid_formats: set[str] = {"text", "json"}
    if debug:
        level: LogLevel = "DEBUG"
    elif verbose:
        level = "INFO"
    elif log_level in valid_levels:
        level = log_level  # type: ignore[assignment]
    else:
        level = "INFO"
    fmt: str = log_format if log_format in valid_formats else "text"
    configure_logging(level=level, sink=log_sink, fmt=fmt)  # type: ignore[arg-type]
    ctx = click.get_current_context()
    ctx.obj = {
        "log_level": log_level,
        "no_color": no_color,
        "json_mode": json_mode,
        "verbose": verbose,
        "debug": debug,
        "log_sink": log_sink,
        "log_format": log_format,
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
app.command("migrate")(migrate_cmd.run)


help_app = typer.Typer(
    name="help",
    help="In-tree documentation surface (e.g. error codes).",
    no_args_is_help=True,
)
help_app.command("error")(help_error_cmd.run)
app.add_typer(help_app, name="help")


def main() -> None:
    app()
