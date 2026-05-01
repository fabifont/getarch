from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner
from getarch.planning.strategies.snapper import SnapperStrategy


def test_snapper_strategy_emits_create_config() -> None:
    cmds = SnapperStrategy().commands()
    assert len(cmds) == 1
    assert cmds[0].argv == ("snapper", "--no-dbus", "-c", "root", "create-config", "/")
    assert cmds[0].chroot is True


def test_planner_adds_snapper_step_and_timers_when_enabled() -> None:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["filesystem"] = {"kind": "btrfs", "label": "system", "snapper": True}
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),
        mount_root=Path("/mnt"),
    )
    ids = [s.id for s in plan.steps]
    assert "snapper" in ids
    services = next(s for s in plan.steps if s.id == "services")
    flat = " ".join(arg for c in services.commands for arg in c.argv)
    assert "snapper-timeline.timer" in flat
    assert "snapper-cleanup.timer" in flat


def test_snapper_rejected_on_non_btrfs_filesystem() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["filesystem"] = {"kind": "ext4", "label": "system", "snapper": True}
    with pytest.raises(ValidationError, match="snapper"):
        Config.model_validate(payload)
