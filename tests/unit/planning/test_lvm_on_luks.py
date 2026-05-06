"""LVM-on-LUKS planner + strategy tests."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import SemanticConfigError
from getarch.planning.planner import Planner
from getarch.planning.strategies.lvm import LvmStrategy, LvmVolumePlan, lv_device_path


def _lvm_payload() -> dict[str, object]:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["filesystem"] = {"kind": "ext4", "label": "system"}
    payload["partitioning"] = {
        "layout": "efi-root",
        "efi_size_mib": 512,
        "lvm": {
            "vg_name": "system",
            "volumes": [
                {"name": "root", "size_mib": 16384, "mountpoint": "/", "filesystem": "ext4"},
                {"name": "home", "size_mib": 8192, "mountpoint": "/home", "filesystem": "ext4"},
                {"name": "var", "mountpoint": "/var", "filesystem": "ext4"},
            ],
        },
    }
    pkgs_in = payload["packages"]
    assert isinstance(pkgs_in, list)
    pkgs: list[str] = [*pkgs_in, "lvm2", "e2fsprogs"]
    payload["packages"] = pkgs
    hooks = [
        "base",
        "systemd",
        "autodetect",
        "modconf",
        "kms",
        "keyboard",
        "sd-vconsole",
        "block",
        "sd-encrypt",
        "lvm2",
        "filesystems",
        "fsck",
    ]
    payload["initramfs"] = {"generator": "mkinitcpio", "hooks": hooks}
    return payload


def test_lvm_strategy_emits_pvcreate_vgcreate_lvcreate() -> None:
    cmds = LvmStrategy(
        pv_device="/dev/mapper/system",
        vg_name="vg0",
        volumes=(
            LvmVolumePlan(name="root", size_mib=16384, mountpoint="/", filesystem="ext4"),
            LvmVolumePlan(name="rest", size_mib=None, mountpoint="/var", filesystem="ext4"),
        ),
    ).commands()
    assert cmds[0].argv[0] == "pvcreate"
    assert "/dev/mapper/system" in cmds[0].argv
    assert cmds[1].argv[0] == "vgcreate"
    assert "vg0" in cmds[1].argv
    assert cmds[2].argv == ("lvcreate", "-y", "-L", "16384M", "-n", "root", "vg0")
    assert cmds[3].argv == ("lvcreate", "-y", "-l", "100%FREE", "-n", "rest", "vg0")


def test_lv_device_path_helper() -> None:
    assert lv_device_path("system", "root") == "/dev/system/root"


def test_planner_emits_lvm_create_step_after_encryption() -> None:
    cfg = Config.model_validate(_lvm_payload())
    validate_semantics(cfg)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    ids = [s.id for s in plan.steps]
    enc = ids.index("encryption")
    lvm = ids.index("lvm-create")
    fs = ids.index("filesystems")
    assert enc < lvm < fs


def test_lvm_filesystem_step_emits_per_lv_mkfs() -> None:
    cfg = Config.model_validate(_lvm_payload())
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    fs = next(s for s in plan.steps if s.id == "filesystems")
    targets = {c.argv[-1] for c in fs.commands if c.argv[0].startswith("mkfs")}
    assert "/dev/system/root" in targets
    assert "/dev/system/home" in targets
    assert "/dev/system/var" in targets
    # ESP also formatted in the same step.
    assert any("EFI" in c.argv[-1] for c in fs.commands)


def test_lvm_mounting_step_orders_root_first() -> None:
    cfg = Config.model_validate(_lvm_payload())
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    mounting = next(s for s in plan.steps if s.id == "mounting")
    mount_targets = [c.argv[-1] for c in mounting.commands if c.argv[0] == "mount"]
    assert mount_targets[0] == "/mnt"
    assert "/mnt/home" in mount_targets
    assert "/mnt/var" in mount_targets


def test_lvm_root_lv_can_be_named_anything() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["lvm"]["volumes"][0]["name"] = "rootfs"  # type: ignore[index]
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    fstab = next(s for s in plan.steps if s.id == "fstab")
    # genfstab runs against the mounted /mnt; just verify the LV got
    # mounted under /mnt by checking the mounting step.
    mounting = next(s for s in plan.steps if s.id == "mounting")
    assert any(c.argv == ("mount", "/dev/system/rootfs", "/mnt") for c in mounting.commands)
    assert fstab.id == "fstab"


def test_semantic_lvm_requires_luks2() -> None:
    payload = _lvm_payload()
    payload["encryption"] = {"kind": "none"}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="luks2"):
        validate_semantics(cfg)


def test_semantic_lvm_requires_lvm2_hook() -> None:
    payload = _lvm_payload()
    initramfs = payload["initramfs"]
    assert isinstance(initramfs, dict)
    hooks_raw = cast("list[str]", initramfs["hooks"])
    initramfs["hooks"] = [h for h in hooks_raw if h != "lvm2"]
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="lvm2"):
        validate_semantics(cfg)


def test_semantic_lvm_conflicts_with_swap_partition() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["layout"] = "efi-swap-root"  # type: ignore[index]
    payload["partitioning"]["swap_size_mib"] = 2048  # type: ignore[index]
    payload["swap"] = {"kind": "partition"}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match=r"swap\.kind='partition'"):
        validate_semantics(cfg)


def test_semantic_lvm_conflicts_with_home_kind() -> None:
    payload = _lvm_payload()
    payload["encryption"]["home_kind"] = "shared-key"  # type: ignore[index]
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="home_kind"):
        validate_semantics(cfg)


def test_schema_lvm_rejects_layout_with_home_role() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["layout"] = "efi-home-root"  # type: ignore[index]
    payload["partitioning"]["home_size_mib"] = 8192  # type: ignore[index]
    with pytest.raises(ValueError, match="lvm conflicts with a 'home'"):
        Config.model_validate(payload)


def test_schema_lvm_requires_root_mountpoint() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["lvm"]["volumes"] = [  # type: ignore[index]
        {"name": "data", "mountpoint": "/data", "filesystem": "ext4"},
    ]
    with pytest.raises(ValueError, match="mountpoint='/'"):
        Config.model_validate(payload)


def test_schema_lvm_rejects_multiple_unsized_volumes() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["lvm"]["volumes"] = [  # type: ignore[index]
        {"name": "root", "mountpoint": "/", "filesystem": "ext4"},
        {"name": "home", "mountpoint": "/home", "filesystem": "ext4"},
    ]
    with pytest.raises(ValueError, match="at most one volume"):
        Config.model_validate(payload)


def test_semantic_lvm_requires_filesystem_packages() -> None:
    payload = _lvm_payload()
    payload["partitioning"]["lvm"]["volumes"][1]["filesystem"] = "btrfs"  # type: ignore[index]
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="btrfs-progs"):
        validate_semantics(cfg)
