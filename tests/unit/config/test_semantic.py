import pytest

from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.errors import SemanticConfigError


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": 1,
        "disk": {"path": "/dev/sda"},
        "partitioning": {"layout": "efi-root", "efi_size_mib": 512},
        "filesystem": {"kind": "ext4", "label": "system"},
        "encryption": {"kind": "none"},
        "swap": {"kind": "none"},
        "kernel": {"kind": "linux"},
        "microcode": {"kind": "auto"},
        "bootloader": {"kind": "systemd-boot", "timeout_seconds": 5},
        "initramfs": {"generator": "mkinitcpio", "hooks": ["base", "udev"]},
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
    base.update(overrides)
    return base


def _cfg(**overrides: object) -> Config:
    return Config.model_validate(_payload(**overrides))


def test_kernel_in_packages_required() -> None:
    cfg = _cfg(packages=["base", "linux-firmware"], kernel={"kind": "linux"})
    with pytest.raises(SemanticConfigError, match="kernel package"):
        validate_semantics(cfg)


def test_locale_lang_must_be_substring_of_locale() -> None:
    cfg = _cfg(
        locale={
            "lang": "fr_FR.UTF-8",
            "locale": "en_US.UTF-8 UTF-8",
            "keymap": "us",
            "timezone": "UTC",
        },
    )
    with pytest.raises(SemanticConfigError, match="locale"):
        validate_semantics(cfg)


def test_luks2_requires_encrypt_hook() -> None:
    cfg = _cfg(
        encryption={"kind": "luks2", "password": "x"},
        initramfs={"generator": "mkinitcpio", "hooks": ["base", "udev", "block"]},
    )
    with pytest.raises(SemanticConfigError, match="encrypt"):
        validate_semantics(cfg)


def test_luks2_with_sd_encrypt_hook_passes() -> None:
    cfg = _cfg(
        encryption={"kind": "luks2", "password": "x"},
        initramfs={
            "generator": "mkinitcpio",
            "hooks": [
                "base",
                "systemd",
                "autodetect",
                "modconf",
                "block",
                "sd-encrypt",
                "filesystems",
                "fsck",
            ],
        },
    )
    validate_semantics(cfg)


def test_swap_partition_requires_swap_layout() -> None:
    cfg = _cfg(swap={"kind": "partition", "size_mib": 2048})
    with pytest.raises(SemanticConfigError, match="layout"):
        validate_semantics(cfg)


def test_btrfs_root_subvolume_required() -> None:
    cfg = _cfg(
        filesystem={
            "kind": "btrfs",
            "label": "system",
            "subvolumes": [{"name": "@home", "mountpoint": "/home"}],
        },
    )
    with pytest.raises(SemanticConfigError, match="root"):
        validate_semantics(cfg)


def test_microcode_explicit_intel_passes_with_no_microcode_in_packages() -> None:
    cfg = _cfg(microcode={"kind": "intel"})
    validate_semantics(cfg)


def test_minimal_valid_config_passes() -> None:
    validate_semantics(_cfg())


def test_home_layout_requires_home_size_mib() -> None:
    cfg = _cfg(
        partitioning={
            "layout": "efi-home-root",
            "efi_size_mib": 512,
            "home_size_mib": None,
        },
    )
    with pytest.raises(SemanticConfigError, match="home_size_mib"):
        validate_semantics(cfg)


def test_luks_with_home_layout_rejected() -> None:
    cfg = _cfg(
        partitioning={
            "layout": "efi-home-root",
            "efi_size_mib": 512,
            "home_size_mib": 4096,
        },
        encryption={"kind": "luks2", "password": "x"},
        filesystem={"kind": "btrfs", "label": "system"},
        initramfs={
            "generator": "mkinitcpio",
            "hooks": ["base", "systemd", "sd-encrypt", "filesystems"],
        },
    )
    with pytest.raises(SemanticConfigError, match="luks2"):
        validate_semantics(cfg)


def test_reflector_requires_non_empty_args() -> None:
    cfg = _cfg(mirrors={"strategy": "reflector", "reflector_args": []})
    with pytest.raises(SemanticConfigError, match="reflector_args"):
        validate_semantics(cfg)


def test_mountpoint_reserved_label_rejected() -> None:
    cfg = _cfg(
        mountpoints=[{"partition_label": "system", "mountpoint": "/srv"}],
    )
    with pytest.raises(SemanticConfigError, match="reserved planner label"):
        validate_semantics(cfg)


def test_mountpoint_root_path_rejected() -> None:
    cfg = _cfg(
        mountpoints=[{"partition_label": "data", "mountpoint": "/home"}],
    )
    with pytest.raises(SemanticConfigError, match="managed"):
        validate_semantics(cfg)


def test_duplicate_mountpoint_partlabel_rejected() -> None:
    cfg = _cfg(
        mountpoints=[
            {"partition_label": "data", "mountpoint": "/srv"},
            {"partition_label": "data", "mountpoint": "/var/data"},
        ],
    )
    with pytest.raises(SemanticConfigError, match="duplicate"):
        validate_semantics(cfg)
