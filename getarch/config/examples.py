"""Built-in example configurations used by the ``examples`` CLI command."""

from __future__ import annotations

import json
from typing import Final

_MINIMAL_EXT4: Final[dict[str, object]] = {
    "version": 1,
    "disk": {"path": "/dev/sda", "wipe_before": False},
    "partitioning": {"layout": "efi-root", "efi_size_mib": 512},
    "filesystem": {"kind": "ext4", "label": "system"},
    "encryption": {"kind": "none"},
    "swap": {"kind": "none"},
    "kernel": {"kind": "linux"},
    "microcode": {"kind": "auto"},
    "bootloader": {"kind": "systemd-boot", "timeout_seconds": 5},
    "initramfs": {
        "generator": "mkinitcpio",
        "hooks": [
            "base",
            "udev",
            "autodetect",
            "modconf",
            "block",
            "filesystems",
            "fsck",
        ],
    },
    "locale": {
        "lang": "en_US.UTF-8",
        "locale": "en_US.UTF-8 UTF-8",
        "keymap": "us",
        "timezone": "UTC",
    },
    "network": {"hostname": "arch", "backend": "networkmanager"},
    "packages": [
        "base",
        "base-devel",
        "linux",
        "linux-firmware",
        "networkmanager",
        "sudo",
        "vim",
    ],
    "services": {"enable": ["NetworkManager"], "timers": ["fstrim.timer"]},
    "mirrors": {"strategy": "keep"},
    "users": {
        "root": {"kind": "prompt"},
        "regular": [],
    },
    "reboot": False,
}

_ENCRYPTED_BTRFS: Final[dict[str, object]] = {
    **_MINIMAL_EXT4,
    "filesystem": {"kind": "btrfs", "label": "system"},
    "encryption": {"kind": "luks2", "password": "CHANGE_ME"},
    "initramfs": {
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
    },
    "users": {
        "root": {"kind": "prompt"},
        "regular": [
            {
                "username": "alice",
                "password": "CHANGE_ME",
                "groups": ["wheel"],
                "sudo": True,
            },
        ],
    },
}


EXAMPLES: Final[dict[str, dict[str, object]]] = {
    "minimal-ext4": _MINIMAL_EXT4,
    "encrypted-btrfs": _ENCRYPTED_BTRFS,
}


def render_example(name: str) -> str:
    if name not in EXAMPLES:
        raise KeyError(f"no example named {name!r}")
    return json.dumps(EXAMPLES[name], indent=2, sort_keys=False)
