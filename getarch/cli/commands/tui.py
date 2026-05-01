"""`getarch tui CONFIG` - launch the Textual plan-viewer TUI."""

from __future__ import annotations

from pathlib import Path

import typer

from getarch.cli.output import GetarchConsole
from getarch.constants import DEFAULT_MOUNT_ROOT


def run(
    config: Path = typer.Argument(..., exists=True),
    mount_root: Path = typer.Option(DEFAULT_MOUNT_ROOT, "--mount-root"),
) -> None:
    """Launch the Textual TUI to browse a config + plan."""
    try:
        from getarch.tui.app import run as run_tui  # noqa: PLC0415
    except ImportError as exc:
        console = GetarchConsole()
        console.error(
            f"TUI dependency missing: {exc}. Install with `pip install 'getarch[tui]'`.",
        )
        raise typer.Exit(code=2) from None
    raise typer.Exit(code=run_tui(config_path=config, mount_root=mount_root))
