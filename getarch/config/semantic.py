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


def _check_kernel_in_packages(cfg: Config) -> None:
    if cfg.kernel.kind not in cfg.packages:
        raise SemanticConfigError(
            f"kernel package {cfg.kernel.kind!r} must be listed in packages",
        )


def _check_locale_consistency(cfg: Config) -> None:
    if cfg.locale.lang not in cfg.locale.locale:
        raise SemanticConfigError(
            f"locale.lang {cfg.locale.lang!r} must be a prefix of locale.locale "
            f"{cfg.locale.locale!r}",
        )


def _check_encryption_initramfs(cfg: Config) -> None:
    if cfg.encryption.kind == "none":
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
