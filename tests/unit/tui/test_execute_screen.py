"""Smoke test: TuiExecuteApp instantiates without running the event loop."""

from __future__ import annotations

import json
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.tui.screens.execute import TuiExecuteApp


def test_execute_app_instantiates(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps(EXAMPLES["minimal-ext4"]))
    app = TuiExecuteApp(config_path=cfg_path, mount_root=Path("/mnt"))
    assert app is not None
