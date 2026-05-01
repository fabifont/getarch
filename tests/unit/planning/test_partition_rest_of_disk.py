from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config, PartitionLayout
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import SemanticConfigError
from getarch.planning.planner import Planner
from getarch.planning.strategies.partitioning import SgdiskStrategy


def _disk() -> Disk:
    return Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)


def test_root_fixed_home_rest_of_disk_partition_order() -> None:
    layout = PartitionLayout(
        layout="efi-home-root",
        efi_size_mib=512,
        root_size_mib=8192,
    )
    cmds = SgdiskStrategy(disk=_disk(), layout=layout, encrypted=False).commands()
    argvs = [c.argv for c in cmds]
    # Root is partition 2 with +8192MiB; home is partition 3 with end "0"
    # (rest of disk).
    assert any("--new=2:0:+8192MiB" in a[1] for a in argvs if a[0] == "sgdisk")
    assert any("--new=3:0:0" in a[1] for a in argvs if a[0] == "sgdisk")
    assert any("--change-name=3:home" in a[1] for a in argvs if a[0] == "sgdisk")


def test_home_fixed_root_rest_of_disk_partition_order() -> None:
    layout = PartitionLayout(
        layout="efi-home-root",
        efi_size_mib=512,
        home_size_mib=4096,
    )
    cmds = SgdiskStrategy(disk=_disk(), layout=layout, encrypted=False).commands()
    argvs = [c.argv for c in cmds]
    # Home is partition 2 with +4096MiB; root is partition 3 with end "0".
    assert any("--new=2:0:+4096MiB" in a[1] for a in argvs if a[0] == "sgdisk")
    assert any("--change-name=2:home" in a[1] for a in argvs if a[0] == "sgdisk")
    assert any("--new=3:0:0" in a[1] for a in argvs if a[0] == "sgdisk")


def test_validator_requires_one_of_home_or_root_size() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {"layout": "efi-home-root", "efi_size_mib": 512}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="root_size_mib"):
        validate_semantics(cfg)


def test_validator_rejects_both_sizes() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "home_size_mib": 4096,
        "root_size_mib": 8192,
    }
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="mutually exclusive"):
        validate_semantics(cfg)


def test_root_size_below_minimum_rejected() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "root_size_mib": 1024,  # < 4096 minimum
    }
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_planner_root_size_path_builds_full_plan() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "root_size_mib": 8192,
    }
    cfg = Config.model_validate(payload)
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    fs_step = next(s for s in plan.steps if s.id == "filesystems")
    flat = " ".join(arg for c in fs_step.commands for arg in c.argv)
    assert "by-partlabel/home" in flat
