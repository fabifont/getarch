"""Planner regression tests pinning behaviours that previously regressed.

* LVM-on-LUKS bootloader cmdline must `root=/dev/<vg>/<lv>` (not the
  LUKS mapper, which is the PV).
* Container packages step must run inside the chroot via Command.chroot.
* Custom layout with role='home' + encrypted home_kind must add the
  encryption-home step in the disk phase.
* Planner auto-adds `lvm2` to packages when partitioning.lvm is set.
"""

from copy import deepcopy
from pathlib import Path
from typing import cast

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner


def _lvm_payload() -> dict[str, object]:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["filesystem"] = {"kind": "ext4", "label": "system"}
    payload["partitioning"] = {
        "layout": "efi-root",
        "efi_size_mib": 512,
        "lvm": {
            "vg_name": "vg0",
            "volumes": [
                {"name": "rootfs", "size_mib": 16384, "mountpoint": "/", "filesystem": "ext4"},
                {"name": "homefs", "mountpoint": "/home", "filesystem": "ext4"},
            ],
        },
    }
    pkgs = cast("list[str]", payload["packages"])
    payload["packages"] = [*pkgs, "e2fsprogs"]
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
            "lvm2",
            "filesystems",
            "fsck",
        ],
    }
    return payload


def test_lvm_bootloader_cmdline_uses_lv_not_mapper() -> None:
    cfg = Config.model_validate(_lvm_payload())
    validate_semantics(cfg)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    boot = next(s for s in plan.steps if s.id == "bootloader")
    flat = (
        " ".join(arg for c in boot.commands for arg in c.argv)
        + " "
        + " ".join(c.input or "" for c in boot.commands)
    )
    # Root must point at the LV, not the LUKS mapper (which is the PV).
    assert "root=/dev/vg0/rootfs" in flat
    assert "root=/dev/mapper/system" not in flat


def test_container_packages_step_runs_under_chroot() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["firmware"] = "container"
    cfg = Config.model_validate(payload)
    plan = Planner().build(cfg=cfg, disk=None, mount_root=Path("/mnt"))
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    cmd = pkgs_step.commands[0]
    assert cmd.chroot is True, "container pacman must run inside arch-chroot"
    assert cmd.argv[0] == "pacman"


def test_custom_layout_encrypted_home_inserts_encryption_home_step() -> None:
    payload = deepcopy(EXAMPLES["encrypted-btrfs"])
    payload["filesystem"] = {"kind": "ext4", "label": "system"}
    payload["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "home_kind": "shared-key",
    }
    payload["partitioning"] = {
        "layout": "efi-root",
        "custom": [
            {"label": "esp", "size_mib": 512, "typecode": "ef00", "role": "efi"},
            {"label": "myhome", "size_mib": 4096, "typecode": "8302", "role": "home"},
            {"label": "cryptbox", "size_mib": None, "typecode": "8300", "role": "root"},
        ],
    }
    pkgs = cast("list[str]", payload["packages"])
    payload["packages"] = [*pkgs, "e2fsprogs"]
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    ids = [s.id for s in plan.steps]
    enc = ids.index("encryption")
    assert "encryption-home" in ids, (
        "custom layout with role='home' + encrypted home_kind must include "
        "the encryption-home step (was previously skipped because the guard "
        "checked the layout string instead of the resolved role)"
    )
    enc_home = ids.index("encryption-home")
    fs = ids.index("filesystems")
    assert enc < enc_home < fs
    # And the LUKS commands target the user's myhome label, not the
    # default "home" partlabel.
    home_step = next(s for s in plan.steps if s.id == "encryption-home")
    flat = " ".join(arg for c in home_step.commands for arg in c.argv)
    assert "/dev/disk/by-partlabel/myhome" in flat


def test_planner_auto_adds_lvm2_when_lvm_configured() -> None:
    payload = _lvm_payload()
    pkgs = cast("list[str]", payload["packages"])
    # Drop lvm2 from packages so the auto-add can prove itself.
    payload["packages"] = [p for p in pkgs if p != "lvm2"]
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    pacstrap_argv = pkgs_step.commands[0].argv
    assert "lvm2" in pacstrap_argv
