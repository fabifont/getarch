"""Textual TUI for browsing a getarch install plan.

Minimal MVP: load a config file, build the plan via the existing
:class:`Planner`, and present each step in a scrollable list view. Per-
step commands collapse and expand. Execution is intentionally NOT wired
yet — the TUI is read-only for now to keep the surface small.

Textual is an optional dependency (``getarch[tui]``); importing this
module triggers the import.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from getarch.config.loader import load_config
from getarch.config.semantic import validate_semantics
from getarch.constants import DEFAULT_MOUNT_ROOT
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_text


class PlanViewer(App[int]):
    """Scrollable read-only view of a config + plan + JSON dump."""

    CSS = """
    Screen { layout: vertical; }
    .pane { padding: 1 2; height: 1fr; }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config_path: Path, mount_root: Path) -> None:
        super().__init__()
        self._config_path = config_path
        self._mount_root = mount_root

    @override
    def compose(self) -> ComposeResult:
        cfg = load_config(self._config_path)
        validate_semantics(cfg)
        plan = Planner().build(
            cfg=cfg,
            disk=Disk(path=DiskPath(Path(cfg.disk.path)), size_bytes=2**40),
            mount_root=self._mount_root,
        )
        rendered = render_text(plan)
        yield Header(show_clock=False)
        with TabbedContent(initial="plan"):
            with TabPane("Plan", id="plan"), Vertical(classes="pane"):
                yield VerticalScroll(Static(rendered))
            with TabPane("Config", id="config"), Vertical(classes="pane"):
                yield VerticalScroll(
                    Static(self._config_path.read_text(encoding="utf-8")),
                )
        yield Footer()


def run(config_path: Path, mount_root: Path = DEFAULT_MOUNT_ROOT) -> int:
    return PlanViewer(config_path=config_path, mount_root=mount_root).run() or 0
