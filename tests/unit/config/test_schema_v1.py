import pytest
from pydantic import ValidationError

from getarch.config.schema.v1 import Config


def _minimal_payload() -> dict[str, object]:
    return {
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
            "timezone": "Europe/Rome",
        },
        "network": {"hostname": "arch", "backend": "networkmanager"},
        "packages": ["base", "linux", "linux-firmware"],
        "services": {"enable": ["NetworkManager"], "timers": ["fstrim.timer"]},
        "mirrors": {"strategy": "keep"},
        "users": {
            "root": {"kind": "prompt"},
            "regular": [],
        },
        "reboot": False,
    }


def test_minimal_payload_parses() -> None:
    cfg = Config.model_validate(_minimal_payload())
    assert cfg.version == 1
    assert cfg.disk.path == "/dev/sda"


def test_extra_fields_forbidden() -> None:
    payload = _minimal_payload()
    payload["extra"] = "no"
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_btrfs_default_subvolumes_present() -> None:
    payload = _minimal_payload()
    payload["filesystem"] = {"kind": "btrfs", "label": "system"}
    cfg = Config.model_validate(payload)
    sub_names = [s.name for s in cfg.filesystem.subvolumes]
    assert sub_names == ["@", "@home", "@snapshots"]


def test_luks2_requires_password() -> None:
    payload = _minimal_payload()
    payload["encryption"] = {"kind": "luks2"}
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_luks2_with_password_ok() -> None:
    payload = _minimal_payload()
    payload["encryption"] = {"kind": "luks2", "password": "p"}
    Config.model_validate(payload)


def test_swapfile_size_required() -> None:
    payload = _minimal_payload()
    payload["swap"] = {"kind": "swapfile"}
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_swapfile_with_size_ok() -> None:
    payload = _minimal_payload()
    payload["swap"] = {"kind": "swapfile", "size_mib": 4096}
    Config.model_validate(payload)


def test_root_auth_plain_requires_password() -> None:
    payload = _minimal_payload()
    payload["users"] = {"root": {"kind": "plain"}, "regular": []}
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_regular_user_requires_username() -> None:
    payload = _minimal_payload()
    payload["users"] = {
        "root": {"kind": "prompt"},
        "regular": [{"groups": ["wheel"]}],
    }
    with pytest.raises(ValidationError):
        Config.model_validate(payload)


def test_partition_layout_separate_home_optional_size() -> None:
    payload = _minimal_payload()
    payload["partitioning"] = {
        "layout": "efi-home-root",
        "efi_size_mib": 512,
        "home_size_mib": None,
    }
    Config.model_validate(payload)
