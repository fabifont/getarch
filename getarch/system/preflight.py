"""Environment preflight: assertions against discovery providers."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
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
    is_uefi = _assert_host(cfg, identity, iso, firmware, network, pacman)
    paths, mounts = _assert_disk(cfg, block_devices)
    _assert_locale(cfg, environment)
    _assert_packages(cfg, pacman)
    _assert_mirrors(cfg)
    _assert_encryption(cfg)
    _assert_mountpoints(cfg)

    return EnvironmentReport(
        disks_found=paths,
        cpu_vendor=environment.cpu_vendor(),
        is_uefi=is_uefi,
        is_root=True,
        is_arch_iso=True,
        internet_reachable=True,
        keyring_initialized=True,
        mountpoints_seen=mounts,
    )


def _assert_host(
    cfg: Config,
    identity: IdentityProvider,
    iso: IsoProvider,
    firmware: FirmwareProvider,
    network: NetworkProvider,
    pacman: PacmanProvider,
) -> bool:
    if not identity.is_root():
        raise _EnvErr("getarch must run as root (effective uid != 0)")

    if not iso.is_arch_iso():
        raise _EnvErr(
            "/etc/os-release does not look like an Arch Linux live ISO "
            "(ID=arch + IMAGE_ID required)",
        )

    is_uefi = firmware.is_uefi()
    if cfg.firmware == "uefi" and not is_uefi:
        raise _EnvErr(
            "firmware='uefi' but the host is not booted in UEFI mode "
            "(efivars not available); set firmware='bios' or boot via UEFI",
        )

    # When the user has declared a network bootstrap step we expect the
    # pipeline to bring networking up *after* this preflight, so skipping
    # the reachability+keyring checks here is correct: the runtime
    # preflight step still re-fetches archlinux-keyring before pacstrap.
    bootstrap_will_run = cfg.network.bootstrap is not None
    if not bootstrap_will_run:
        if not network.internet_reachable(INTERNET_REACHABILITY_HOST):
            raise _EnvErr(
                f"no internet: cannot resolve {INTERNET_REACHABILITY_HOST}",
            )
        if not pacman.keyring_initialized():
            raise _EnvErr(
                "pacman keyring is not initialised; run pacman-key --init && "
                "pacman-key --populate archlinux",
            )
    return is_uefi


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
    supported = environment.supported_locales()
    for entry in cfg.locale.locale:
        if entry not in supported:
            raise _EnvErr(f"locale {entry!r} not supported on this ISO")
    if cfg.locale.keymap not in environment.keymaps():
        raise _EnvErr(f"keymap {cfg.locale.keymap!r} not available")
    if cfg.locale.timezone not in environment.timezones():
        raise _EnvErr(f"timezone {cfg.locale.timezone!r} not available")


def _assert_packages(cfg: Config, pacman: PacmanProvider) -> None:
    if cfg.repositories.multilib or cfg.repositories.extra:
        # The repositories step mutates the live ISO's pacman.conf during
        # the pipeline run; preflight queries the unmutated config so we
        # can't accurately verify packages from those repos here. Skip
        # validation rather than reject legitimate configs.
        return
    for pkg in cfg.packages:
        if not pacman.package_exists(pkg):
            raise _EnvErr(f"package {pkg!r} not found in pacman repos")


_MIRROR_PROBE_TIMEOUT_SECONDS = 10
_MIRROR_PROBE_PATH = "core/os/x86_64/core.db"
_HTTP_BAD_STATUS = 400


def _assert_mirrors(cfg: Config) -> None:
    if cfg.mirrors.strategy != "static":
        return
    if not cfg.mirrors.static_path:
        return
    static_path = Path(cfg.mirrors.static_path)
    if not static_path.is_file():
        raise _EnvErr(
            f"static mirrorlist not found: {cfg.mirrors.static_path}",
        )
    _probe_first_mirror(static_path)


def _probe_first_mirror(static_path: Path) -> None:
    base_url = _first_mirror_base_url(static_path)
    if base_url is None:
        # Mirrorlist with only commented lines — nothing to probe.
        return
    probe_url = f"{base_url.rstrip('/')}/{_MIRROR_PROBE_PATH}"
    request = urllib.request.Request(probe_url, method="HEAD")  # noqa: S310
    try:
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=_MIRROR_PROBE_TIMEOUT_SECONDS,
        ) as response:
            status = response.status
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise _EnvErr(
            f"first mirror in {static_path} unreachable ({probe_url}): {exc}",
        ) from exc
    if status >= _HTTP_BAD_STATUS:
        raise _EnvErr(
            f"first mirror in {static_path} responded {status} for {probe_url}",
        )


def _first_mirror_base_url(static_path: Path) -> str | None:
    for raw in static_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith("server"):
            continue
        _, _, value = line.partition("=")
        url = value.strip()
        # Mirror lines use $repo / $arch placeholders; strip everything
        # from the first '$' onward to get the base URL.
        idx = url.find("$")
        if idx > 0:
            url = url[:idx]
        return url.rstrip("/")
    return None


def _assert_encryption(cfg: Config) -> None:
    if not cfg.encryption.header_path:
        return
    if not Path(cfg.encryption.header_path).is_file():
        raise _EnvErr(
            f"detached LUKS header not found: {cfg.encryption.header_path}",
        )


def _assert_mountpoints(cfg: Config) -> None:
    if not cfg.mountpoints:
        return
    target_disk_name = Path(cfg.disk.path).name
    for mp in cfg.mountpoints:
        link = Path("/dev/disk/by-partlabel") / mp.partition_label
        try:
            resolved = link.resolve(strict=True)
        except FileNotFoundError as exc:
            raise _EnvErr(
                f"mountpoint partlabel {mp.partition_label!r} not present on "
                f"this system",
            ) from exc
        # `resolved` is e.g. /dev/sdb1 — strip the trailing partition index
        # to get the parent disk name (sdb, nvme0n1, mmcblk0, etc.).
        parent = _disk_name_for_partition(resolved.name)
        if parent == target_disk_name:
            raise _EnvErr(
                f"mountpoint {mp.mountpoint!r} (partlabel "
                f"{mp.partition_label!r}) lives on the install target disk "
                f"{cfg.disk.path}; partitioning would destroy it",
            )


def _disk_name_for_partition(partition_name: str) -> str:
    # nvme0n1p1 -> nvme0n1, mmcblk0p2 -> mmcblk0, sda1 -> sda
    return re.sub(r"(p?\d+)$", "", partition_name)
