"""Container/chroot install mode planner tests."""

from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.errors import PlanError, SemanticConfigError
from getarch.planning.planner import Planner


def _container_payload() -> dict[str, object]:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["firmware"] = "container"
    return payload


def test_planner_container_plan_skips_disk_and_boot_steps() -> None:
    cfg = Config.model_validate(_container_payload())
    plan = Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))
    ids = {s.id for s in plan.steps}
    # Disk-side and boot-side concerns are gone.
    skipped_steps = (
        "partitioning",
        "encryption",
        "filesystems",
        "mounting",
        "bootloader",
        "initramfs",
        "fstab",
        "swap",
        "cleanup",
        "reboot",
    )
    for skipped in skipped_steps:
        assert skipped not in ids, f"unexpected step {skipped} in container plan"


def test_planner_container_plan_keeps_packages_and_users() -> None:
    cfg = Config.model_validate(_container_payload())
    plan = Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))
    ids = [s.id for s in plan.steps]
    assert "packages" in ids
    assert "users" in ids
    assert "system_config" in ids


def test_container_packages_step_uses_pacman_not_pacstrap() -> None:
    cfg = Config.model_validate(_container_payload())
    plan = Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    argv = pkgs_step.commands[0].argv
    assert argv[0] == "pacman"
    assert "-Sy" in argv
    assert "--noconfirm" in argv
    assert "--needed" in argv


def test_container_packages_step_auto_adds_networkmanager() -> None:
    payload = _container_payload()
    pkgs_in = cast("list[str]", payload["packages"])
    payload["packages"] = [p for p in pkgs_in if p != "networkmanager"]
    cfg = Config.model_validate(payload)
    plan = Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "networkmanager" in pkgs_step.commands[0].argv


def test_planner_rejects_missing_disk_for_non_container() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    cfg = Config.model_validate(payload)
    with pytest.raises(PlanError, match="disk is required"):
        Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))


def test_semantic_container_rejects_encryption() -> None:
    payload = _container_payload()
    payload["encryption"] = {"kind": "luks2", "password": "x"}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="encryption"):
        validate_semantics(cfg)


def test_semantic_container_rejects_swap_partition() -> None:
    payload = _container_payload()
    payload["swap"] = {"kind": "partition"}
    payload["partitioning"] = {"layout": "efi-swap-root", "swap_size_mib": 1024}
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="swap partition"):
        validate_semantics(cfg)


def test_semantic_container_rejects_lvm() -> None:
    payload = _container_payload()
    payload["partitioning"] = {
        "layout": "efi-root",
        "lvm": {
            "vg_name": "vg",
            "volumes": [{"name": "r", "mountpoint": "/", "filesystem": "ext4"}],
        },
    }
    cfg = Config.model_validate(payload)
    with pytest.raises(SemanticConfigError, match="lvm"):
        validate_semantics(cfg)
