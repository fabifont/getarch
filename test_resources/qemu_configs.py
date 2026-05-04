"""Emit getarch JSON configs tuned for the QEMU smoke matrix.

Usage:
    python test_resources/qemu_configs.py <fs> <bootloader> > config.json

Where ``fs`` is one of ``ext4``/``btrfs``/``xfs``/``f2fs`` and ``bootloader``
is one of ``systemd-boot``/``grub``/``uki``. The emitted config targets
``/dev/vda``, the only disk QEMU exposes via ``-drive if=virtio``.

The configs intentionally avoid LUKS (kept for a separate matrix run) and
use ``microcode.kind = "none"`` because the QEMU CPU vendor is not Intel
or AMD as far as ``/proc/cpuinfo`` is concerned.
"""

from __future__ import annotations

import json
import sys
from typing import Final

_DRACUT_HOOKS: Final[list[str]] = []  # dracut ignores hooks
_MKINITCPIO_DEFAULT_HOOKS: Final[list[str]] = [
    "base",
    "udev",
    "autodetect",
    "modconf",
    "block",
    "filesystems",
    "fsck",
]
_MKINITCPIO_F2FS_HOOKS: Final[list[str]] = [
    *_MKINITCPIO_DEFAULT_HOOKS,
]


def build(fs: str, bootloader: str) -> dict[str, object]:
    if fs not in {"ext4", "btrfs", "xfs", "f2fs"}:
        raise SystemExit(f"unknown filesystem {fs!r}")
    if bootloader not in {"systemd-boot", "grub", "uki"}:
        raise SystemExit(f"unknown bootloader {bootloader!r}")

    packages = [
        "base",
        "base-devel",
        "linux",
        "linux-firmware",
        "networkmanager",
        "sudo",
    ]
    if fs == "btrfs":
        packages.append("btrfs-progs")
    elif fs == "xfs":
        packages.append("xfsprogs")
    elif fs == "f2fs":
        packages.append("f2fs-tools")
    if bootloader == "grub":
        packages.append("grub")
        packages.append("efibootmgr")
    elif bootloader == "uki":
        packages.append("efibootmgr")

    initramfs_hooks = (
        _MKINITCPIO_F2FS_HOOKS if fs == "f2fs" else _MKINITCPIO_DEFAULT_HOOKS
    )

    cfg: dict[str, object] = {
        "version": 1,
        "disk": {"path": "/dev/vda", "wipe_before": True},
        "partitioning": {"layout": "efi-root", "efi_size_mib": 512},
        "filesystem": {"kind": fs, "label": "system"},
        "encryption": {"kind": "none"},
        "swap": {"kind": "none"},
        "kernel": {"kind": "linux"},
        "microcode": {"kind": "none"},
        "bootloader": {
            "kind": bootloader,
            "entry_id": "arch",
            "timeout_seconds": 1,
            # Send installed-system kernel output to ttyS0 so the
            # post-install reboot-check (file:-mode serial) actually
            # captures the login prompt. Without this, the kernel only
            # writes to tty0 (framebuffer) and the reboot check times
            # out at 10 minutes with an empty serial-boot.log.
            "extra_kernel_params": ["console=ttyS0,115200", "console=tty0"],
        },
        "initramfs": {
            "generator": "mkinitcpio",
            "hooks": initramfs_hooks,
        },
        "locale": {
            "lang": "en_US.UTF-8",
            "locale": "en_US.UTF-8 UTF-8",
            "keymap": "us",
            "timezone": "UTC",
        },
        "network": {"hostname": "qemu-arch", "backend": "networkmanager"},
        "packages": packages,
        # Smoke matrix uses the virtfs share for control, not SSH, so
        # openssh + sshd are intentionally absent. Only NetworkManager so
        # the installed system has DHCP on first boot.
        "services": {"enable": ["NetworkManager"], "timers": []},
        "mirrors": {"strategy": "keep"},
        "users": {
            "root": {"kind": "plain", "password": "a"},
            "regular": [],
        },
        "reboot": False,
    }
    return cfg


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: qemu_configs.py <fs> <bootloader>")
    cfg = build(sys.argv[1], sys.argv[2])
    json.dump(cfg, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
