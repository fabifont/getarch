"""Environment preflight: assertions against discovery providers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.config.schema.v1 import Config
from getarch.constants import INTERNET_REACHABILITY_HOST
from getarch.errors import EnvironmentError as _EnvErr
from getarch.system.discovery import (
    BlockDeviceProvider,
    EnvironmentProvider,
    FirmwareProvider,
    IdentityProvider,
    IsoProvider,
    NetworkProvider,
    PacmanProvider,
)


@dataclass(frozen=True, slots=True)
class EnvironmentReport:
    disks_found: dict[str, int]
    cpu_vendor: str | None
    is_uefi: bool
    is_root: bool
    is_arch_iso: bool
    internet_reachable: bool
    keyring_initialized: bool
    mountpoints_seen: tuple[str, ...]


def preflight_environment(
    cfg: Config,
    block_devices: BlockDeviceProvider,
    environment: EnvironmentProvider,
    firmware: FirmwareProvider,
    pacman: PacmanProvider,
    identity: IdentityProvider,
    iso: IsoProvider,
    network: NetworkProvider,
) -> EnvironmentReport:
    _assert_host(identity, iso, firmware, network, pacman)
    paths, mounts = _assert_disk(cfg, block_devices)
    _assert_locale(cfg, environment)
    _assert_packages(cfg, pacman)
    _assert_mirrors(cfg)

    return EnvironmentReport(
        disks_found=paths,
        cpu_vendor=environment.cpu_vendor(),
        is_uefi=True,
        is_root=True,
        is_arch_iso=True,
        internet_reachable=True,
        keyring_initialized=True,
        mountpoints_seen=mounts,
    )


def _assert_host(
    identity: IdentityProvider,
    iso: IsoProvider,
    firmware: FirmwareProvider,
    network: NetworkProvider,
    pacman: PacmanProvider,
) -> None:
    if not identity.is_root():
        raise _EnvErr("getarch must run as root (effective uid != 0)")

    if not iso.is_arch_iso():
        raise _EnvErr(
            "/etc/os-release does not look like an Arch Linux live ISO "
            "(ID=arch + IMAGE_ID required)",
        )

    if not firmware.is_uefi():
        raise _EnvErr("system is not booted in UEFI mode (efivars not available)")

    if not network.internet_reachable(INTERNET_REACHABILITY_HOST):
        raise _EnvErr(
            f"no internet: cannot resolve {INTERNET_REACHABILITY_HOST}",
        )

    if not pacman.keyring_initialized():
        raise _EnvErr(
            "pacman keyring is not initialised; run pacman-key --init && "
            "pacman-key --populate archlinux",
        )


def _assert_disk(
    cfg: Config,
    block_devices: BlockDeviceProvider,
) -> tuple[dict[str, int], tuple[str, ...]]:
    disks = block_devices.list_disks()
    paths = {d.path.as_posix(): d.size_bytes for d in disks}
    if cfg.disk.path not in paths:
        raise _EnvErr(f"target disk {cfg.disk.path} not present; saw {sorted(paths)}")

    mounts = block_devices.target_disk_busy(cfg.disk.path)
    if mounts:
        raise _EnvErr(
            f"target disk {cfg.disk.path} has mounted partitions: {', '.join(mounts)}",
        )
    return paths, mounts


def _assert_locale(cfg: Config, environment: EnvironmentProvider) -> None:
    if cfg.locale.locale not in environment.supported_locales():
        raise _EnvErr(f"locale {cfg.locale.locale!r} not supported on this ISO")
    if cfg.locale.keymap not in environment.keymaps():
        raise _EnvErr(f"keymap {cfg.locale.keymap!r} not available")
    if cfg.locale.timezone not in environment.timezones():
        raise _EnvErr(f"timezone {cfg.locale.timezone!r} not available")


def _assert_packages(cfg: Config, pacman: PacmanProvider) -> None:
    for pkg in cfg.packages:
        if not pacman.package_exists(pkg):
            raise _EnvErr(f"package {pkg!r} not found in pacman repos")


def _assert_mirrors(cfg: Config) -> None:
    if cfg.mirrors.strategy != "static":
        return
    if not cfg.mirrors.static_path:
        return
    if not Path(cfg.mirrors.static_path).is_file():
        raise _EnvErr(
            f"static mirrorlist not found: {cfg.mirrors.static_path}",
        )
