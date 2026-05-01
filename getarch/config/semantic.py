"""Semantic validation - cross-section rules that Pydantic alone cannot express."""

from __future__ import annotations

from getarch.config.schema.v1 import Config
from getarch.errors import SemanticConfigError


def validate_semantics(cfg: Config) -> None:
    _check_kernel_in_packages(cfg)
    _check_locale_consistency(cfg)
    _check_encryption_initramfs(cfg)
    _check_swap_layout(cfg)
    _check_btrfs_subvolumes(cfg)
    _check_mirrors(cfg)
    _check_home_layout(cfg)
    _check_luks_home_incompatible(cfg)
    _check_mountpoints(cfg)
    _check_firmware_bootloader(cfg)


def _check_kernel_in_packages(cfg: Config) -> None:
    if cfg.kernel.kind not in cfg.packages:
        raise SemanticConfigError(
            f"kernel package {cfg.kernel.kind!r} must be listed in packages",
        )


def _check_locale_consistency(cfg: Config) -> None:
    if not any(cfg.locale.lang in entry for entry in cfg.locale.locale):
        raise SemanticConfigError(
            f"locale.lang {cfg.locale.lang!r} must be a prefix of at least one "
            f"entry in locale.locale {cfg.locale.locale!r}",
        )


def _check_encryption_initramfs(cfg: Config) -> None:
    if cfg.encryption.kind == "none":
        return
    if cfg.initramfs.generator != "mkinitcpio":
        # dracut auto-discovers LUKS roots from kernel cmdline; no hook list.
        return
    hooks = set(cfg.initramfs.hooks)
    if "encrypt" not in hooks and "sd-encrypt" not in hooks:
        raise SemanticConfigError(
            "luks2 requires 'encrypt' (busybox) or 'sd-encrypt' (systemd) in initramfs.hooks",
        )


def _check_swap_layout(cfg: Config) -> None:
    if cfg.swap.kind == "partition" and "swap" not in cfg.partitioning.layout:
        raise SemanticConfigError(
            f"swap.kind=partition requires a partition layout that includes swap; "
            f"got {cfg.partitioning.layout!r}",
        )


def _check_btrfs_subvolumes(cfg: Config) -> None:
    if cfg.filesystem.kind != "btrfs":
        return
    mountpoints = {s.mountpoint for s in cfg.filesystem.subvolumes}
    if "/" not in mountpoints:
        raise SemanticConfigError(
            "btrfs configuration must include a subvolume mounted at '/' (root)",
        )


def _check_mirrors(cfg: Config) -> None:
    if cfg.mirrors.strategy == "reflector" and not cfg.mirrors.reflector_args:
        raise SemanticConfigError(
            "mirrors.strategy='reflector' requires non-empty reflector_args; "
            "consider ['--latest', '20', '--protocol', 'https', '--sort', 'rate']",
        )


def _check_home_layout(cfg: Config) -> None:
    if "home" in cfg.partitioning.layout and cfg.partitioning.home_size_mib is None:
        raise SemanticConfigError(
            f"partitioning.layout={cfg.partitioning.layout!r} requires "
            "partitioning.home_size_mib (rest-of-disk auto-allocation is not "
            "implemented yet)",
        )


def _check_luks_home_incompatible(cfg: Config) -> None:
    if cfg.encryption.kind == "luks2" and "home" in cfg.partitioning.layout:
        raise SemanticConfigError(
            "encryption.kind='luks2' with a separate /home partition is not "
            "supported yet: only the root partition would be encrypted, leaving "
            "user data on a plaintext /home. Use a layout without 'home' "
            "(e.g. efi-root or efi-swap-root) and rely on a /home subvolume, "
            "or wait for encrypted-home support.",
        )


_RESERVED_PARTLABELS = frozenset({"EFI", "system", "cryptsystem", "swap", "home"})


def _check_mountpoints(cfg: Config) -> None:
    seen_labels: set[str] = set()
    seen_mounts: set[str] = set()
    for mp in cfg.mountpoints:
        if mp.partition_label in _RESERVED_PARTLABELS:
            raise SemanticConfigError(
                f"mountpoint partition_label {mp.partition_label!r} collides "
                f"with reserved planner label",
            )
        if mp.partition_label in seen_labels:
            raise SemanticConfigError(
                f"duplicate mountpoint partition_label {mp.partition_label!r}",
            )
        if mp.mountpoint in {"/", "/boot", "/home"}:
            raise SemanticConfigError(
                f"mountpoint {mp.mountpoint!r} is managed by the planner; "
                f"do not declare it under mountpoints",
            )
        if mp.mountpoint in seen_mounts:
            raise SemanticConfigError(f"duplicate mountpoint {mp.mountpoint!r}")
        seen_labels.add(mp.partition_label)
        seen_mounts.add(mp.mountpoint)


def _check_firmware_bootloader(cfg: Config) -> None:
    if cfg.firmware == "bios" and cfg.bootloader.kind != "grub":
        raise SemanticConfigError(
            f"firmware='bios' requires bootloader.kind='grub'; got "
            f"{cfg.bootloader.kind!r}",
        )
