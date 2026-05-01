"""Smoke tests for the TUI: instantiate without running the event loop."""

from __future__ import annotations

import json
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.tui.app import PlanViewer


def test_plan_viewer_instantiates(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = PlanViewer(config_path=cfg_path, mount_root=Path("/mnt"))
    # Compose touches the planner; running the event loop requires a TTY,
    # so we just confirm the constructor wiring is intact.
    assert app is not None
