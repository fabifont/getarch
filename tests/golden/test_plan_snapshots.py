from pathlib import Path

from syrupy.assertion import SnapshotAssertion

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner
from getarch.planning.rendering import render_json


def test_minimal_ext4_plan_snapshot(snapshot: SnapshotAssertion) -> None:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    disk = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)
    plan_json = render_json(
        Planner().build(cfg=cfg, disk=disk, mount_root=Path("/mnt"))
    )
    assert plan_json == snapshot


def test_encrypted_btrfs_plan_snapshot(snapshot: SnapshotAssertion) -> None:
    cfg = Config.model_validate(EXAMPLES["encrypted-btrfs"])
    disk = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)
    plan_json = render_json(
        Planner().build(cfg=cfg, disk=disk, mount_root=Path("/mnt"))
    )
    assert plan_json == snapshot
