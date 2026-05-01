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
            "Execute the install pipeline live in the TUI. Currently runs "
            "in dry-run mode; real execution requires modal confirmations "
            "(tracked in the roadmap)."
        ),
    ),
) -> None:
    """Launch the Textual TUI to browse a config + plan, or live-execute."""
    try:
        if execute:
            from getarch.tui.screens.execute import run as run_tui  # noqa: PLC0415
        else:
            from getarch.tui.app import run as run_tui  # noqa: PLC0415
    except ImportError as exc:
        console = GetarchConsole()
        console.error(
            f"TUI dependency missing: {exc}. Install with `pip install 'getarch[tui]'`.",
        )
        raise typer.Exit(code=2) from None
    raise typer.Exit(code=run_tui(config_path=config, mount_root=mount_root))
