import json
from pathlib import Path

import pytest

from getarch.config.loader import load_config
from getarch.errors import SyntacticConfigError

_FULL: dict[str, object] = {
    "version": 1,
    "disk": {"path": "/dev/sda"},
    "partitioning": {"layout": "efi-root", "efi_size_mib": 512},
    "filesystem": {"kind": "ext4", "label": "system"},
    "encryption": {"kind": "none"},
    "swap": {"kind": "none"},
    "kernel": {"kind": "linux"},
    "microcode": {"kind": "auto"},
    "bootloader": {"kind": "systemd-boot", "timeout_seconds": 5},
    "initramfs": {"generator": "mkinitcpio", "hooks": ["base", "udev", "autodetect"]},
    "locale": {
        "lang": "en_US.UTF-8",
        "locale": "en_US.UTF-8 UTF-8",
        "keymap": "us",
        "timezone": "Europe/Rome",
    },
    "network": {"hostname": "arch"},
    "packages": ["base", "linux", "linux-firmware"],
    "services": {"enable": [], "timers": []},
    "mirrors": {"strategy": "keep"},
    "users": {"root": {"kind": "prompt"}, "regular": []},
    "reboot": False,
}


def test_load_config_from_json(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps(_FULL))
    cfg = load_config(p)
    assert cfg.version == 1


def test_load_config_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text("{not json")
    with pytest.raises(SyntacticConfigError):
        load_config(p)


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SyntacticConfigError):
        load_config(tmp_path / "missing.json")


def test_load_config_unsupported_version(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"version": 99}))
    with pytest.raises(SyntacticConfigError):
        load_config(p)
