"""`getarch tui CONFIG` - launch the Textual plan-viewer or live-run TUI."""

from __future__ import annotations

from pathlib import Path

import typer

from getarch.cli.output import GetarchConsole
from getarch.constants import DEFAULT_MOUNT_ROOT


def run(
    config: Path = typer.Argument(..., exists=True),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
    execute: bool = typer.Option(
        False,
        "--execute",
        help=(
            "Execute the install pipeline live in the TUI. Defaults to "
            "dry-run; pass --no-dry-run to run for real (a modal "
            "confirmation gates destructive plans)."
        ),
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help=(
            "When combined with --execute: run with DryRunner (default) "
            "or RealRunner. The destructive-plan modal is shown only when "
            "--no-dry-run is set."
        ),
    ),
    assume_yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the destructive-plan modal (--execute --no-dry-run only).",
    ),
) -> None:
    """Launch the Textual TUI to browse a config + plan, or live-execute."""
    try:
        if execute:
            from getarch.tui.screens.execute import run as run_execute  # noqa: PLC0415

            raise typer.Exit(
                code=run_execute(
                    config_path=config,
                    mount_root=mount_root,
                    dry_run=dry_run,
                    assume_yes=assume_yes,
                ),
            )
        from getarch.tui.app import run as run_browser  # noqa: PLC0415
    except ImportError as exc:
        console = GetarchConsole()
        console.error(
            f"TUI dependency missing: {exc}. Install with `pip install 'getarch[tui]'`.",
        )
        raise typer.Exit(code=2) from None
    raise typer.Exit(code=run_browser(config_path=config, mount_root=mount_root))
