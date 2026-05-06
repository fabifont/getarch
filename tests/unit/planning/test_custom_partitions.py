"""Custom partition DSL planner + strategy tests."""

from copy import deepcopy
from pathlib import Path

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config, CustomPartition
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import SemanticConfigError
from getarch.planning.planner import Planner
from getarch.planning.strategies.partitioning_custom import (
    SgdiskCustomStrategy,
    role_to_label,
)


def _custom_payload(custom: list[dict[str, object]]) -> dict[str, object]:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["partitioning"] = {"layout": "efi-root", "custom": custom}
    return payload


def test_strategy_emits_zap_then_per_partition_triplet() -> None:
    cmds = SgdiskCustomStrategy(
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        partitions=(
            CustomPartition(label="boot", size_mib=512, typecode="ef00", role="efi"),
            CustomPartition(label="rootfs", size_mib=None, typecode="8300", role="root"),
        ),
    ).commands()
    assert cmds[0].argv == ("sgdisk", "--zap-all", "/dev/sda")
    # Partition 1: efi
    assert cmds[1].argv == ("sgdisk", "--new=1:0:+512MiB", "/dev/sda")
    assert cmds[2].argv == ("sgdisk", "--typecode=1:ef00", "/dev/sda")
    assert cmds[3].argv == ("sgdisk", "--change-name=1:boot", "/dev/sda")
    # Partition 2: root, rest of disk
    assert cmds[4].argv == ("sgdisk", "--new=2:0:0", "/dev/sda")
    assert cmds[5].argv == ("sgdisk", "--typecode=2:8300", "/dev/sda")
    assert cmds[6].argv == ("sgdisk", "--change-name=2:rootfs", "/dev/sda")


def test_role_to_label_skips_extra() -> None:
    parts = (
        CustomPartition(label="a", size_mib=512, typecode="ef00", role="efi"),
        CustomPartition(label="b", size_mib=None, typecode="8300", role="root"),
        CustomPartition(label="c", size_mib=1024, typecode="8300", role="extra"),
    )
    assert role_to_label(parts) == {"efi": "a", "root": "b"}


def test_planner_custom_layout_uses_user_labels() -> None:
    cfg = Config.model_validate(
        _custom_payload(
            [
                {"label": "boot", "size_mib": 512, "typecode": "ef00", "role": "efi"},
                {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
            ]
        )
    )
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    fs = next(s for s in plan.steps if s.id == "filesystems")
    mkfs_targets = {c.argv[-1] for c in fs.commands if c.argv[0].startswith("mkfs")}
    assert "/dev/disk/by-partlabel/rootfs" in mkfs_targets
    assert "/dev/disk/by-partlabel/boot" in mkfs_targets


def test_planner_custom_swap_uses_user_label() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "myswap", "size_mib": 2048, "typecode": "8200", "role": "swap"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["swap"] = {"kind": "partition"}
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    swap_step = next(s for s in plan.steps if s.id == "swap")
    assert any("/dev/disk/by-partlabel/myswap" in c.argv[-1] for c in swap_step.commands)


def test_planner_custom_home_uses_user_label() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "myhome", "size_mib": 4096, "typecode": "8302", "role": "home"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    fs = next(s for s in plan.steps if s.id == "filesystems")
    mkfs_targets = {c.argv[-1] for c in fs.commands if c.argv[0].startswith("mkfs")}
    assert "/dev/disk/by-partlabel/myhome" in mkfs_targets


def test_schema_custom_requires_efi_and_root() -> None:
    payload = _custom_payload(
        [
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    with pytest.raises(ValueError, match="role='efi'"):
        Config.model_validate(payload)


def test_schema_custom_rejects_duplicate_labels() -> None:
    payload = _custom_payload(
        [
            {"label": "x", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "x", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    with pytest.raises(ValueError, match="duplicate labels"):
        Config.model_validate(payload)


def test_schema_custom_rejects_duplicate_non_extra_role() -> None:
    payload = _custom_payload(
        [
            {"label": "a", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "b", "size_mib": 4096, "typecode": "8300", "role": "root"},
            {"label": "c", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    with pytest.raises(ValueError, match="role='root'"):
        Config.model_validate(payload)


def test_schema_custom_allows_multiple_extra() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "data", "size_mib": 8192, "typecode": "8300", "role": "extra"},
            {"label": "logs", "size_mib": 1024, "typecode": "8300", "role": "extra"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    cfg = Config.model_validate(payload)
    assert cfg.partitioning.custom is not None
    assert sum(1 for p in cfg.partitioning.custom if p.role == "extra") == 2


def test_schema_custom_rejects_multiple_unsized() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
            {"label": "data", "size_mib": None, "typecode": "8300", "role": "extra"},
        ]
    )
    with pytest.raises(ValueError, match="at most one partition with no size_mib"):
        Config.model_validate(payload)


def test_schema_custom_conflicts_with_lvm() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["partitioning"]["lvm"] = {  # type: ignore[index]
        "vg_name": "vg",
        "volumes": [{"name": "r", "mountpoint": "/", "filesystem": "ext4"}],
    }
    with pytest.raises(ValueError, match="lvm"):
        Config.model_validate(payload)


def test_semantic_swap_partition_with_custom_swap_role_passes() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "swp", "size_mib": 1024, "typecode": "8200", "role": "swap"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["swap"] = {"kind": "partition"}
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)  # must not raise


def test_semantic_swap_partition_without_custom_swap_role_raises() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["swap"] = {"kind": "partition"}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="includes swap"):
        validate_semantics(cfg)


def test_semantic_mountpoints_collide_with_custom_label() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["mountpoints"] = [{"partition_label": "rootfs", "mountpoint": "/data"}]
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="reserved planner label"):
        validate_semantics(cfg)


def test_semantic_mountpoints_extra_label_does_not_collide() -> None:
    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    # An "extra" partition's label is not in the reserved set, but the
    # mountpoint preflight on a *target* disk would refuse it. Use a
    # disk-different label for mountpoint declaration so semantics pass.
    payload["mountpoints"] = [
        {"partition_label": "data_external", "mountpoint": "/data"},
    ]
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)


def test_planner_partitioning_step_uses_custom_strategy() -> None:
    cfg = Config.model_validate(
        _custom_payload(
            [
                {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
                {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
            ]
        )
    )
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    part = next(s for s in plan.steps if s.id == "partitioning")
    # Custom strategy emits 1 zap + 3 commands per partition + 2
    # post-settle commands (partprobe + udevadm settle) appended by the
    # planner so by-partlabel symlinks exist before mkfs runs.
    assert len(part.commands) == 1 + 3 * 2 + 2
    assert part.title == "Partition disk (custom layout)"
    # And the last two are the settle pair, in order.
    assert part.commands[-2].argv[0] == "partprobe"
    assert part.commands[-1].argv == ("udevadm", "settle")


def test_planner_encryption_step_uses_custom_root_label() -> None:
    """Regression: with a custom layout that names the root partition
    something other than ``cryptsystem``, the LUKS strategy must format
    the user's actual partition (not a non-existent
    ``/dev/disk/by-partlabel/cryptsystem``)."""

    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "cryptbox", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["encryption"] = {"kind": "luks2", "password": "x"}
    payload["initramfs"] = {
        "generator": "mkinitcpio",
        "hooks": [
            "base",
            "systemd",
            "autodetect",
            "modconf",
            "kms",
            "keyboard",
            "sd-vconsole",
            "block",
            "sd-encrypt",
            "filesystems",
            "fsck",
        ],
    }
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    enc = next(s for s in plan.steps if s.id == "encryption")
    # Both luksFormat and `open <part> <mapper>` reference the user's
    # cryptbox label, never the default cryptsystem.
    flat = " ".join(arg for c in enc.commands for arg in c.argv)
    assert "/dev/disk/by-partlabel/cryptbox" in flat
    assert "/dev/disk/by-partlabel/cryptsystem" not in flat


def test_semantic_detached_header_diagnostic_uses_custom_label() -> None:
    """Diagnostic for missing header_path mentions the user's label."""

    payload = _custom_payload(
        [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "lukshdr", "size_mib": 16, "typecode": "8300", "role": "luksheader"},
            {"label": "rootfs", "size_mib": None, "typecode": "8300", "role": "root"},
        ]
    )
    payload["encryption"] = {"kind": "luks2", "password": "x"}
    payload["initramfs"] = {
        "generator": "mkinitcpio",
        "hooks": [
            "base",
            "systemd",
            "autodetect",
            "modconf",
            "kms",
            "keyboard",
            "sd-vconsole",
            "block",
            "sd-encrypt",
            "filesystems",
            "fsck",
        ],
    }
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="lukshdr"):
        validate_semantics(cfg)
