from pathlib import Path

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import EnvironmentError as EnvErr
from getarch.system.preflight import EnvironmentReport, preflight_environment


class _BD:
    def __init__(
        self,
        disks: tuple[Disk, ...],
        mounts: tuple[str, ...] = (),
    ) -> None:
        self._d = disks
        self._m = mounts

    def list_disks(self) -> tuple[Disk, ...]:
        return self._d

    def target_disk_busy(self, path: str) -> tuple[str, ...]:
        del path
        return self._m


class _Env:
    def __init__(
        self,
        locales: tuple[str, ...] = ("en_US.UTF-8 UTF-8",),
        keymaps: tuple[str, ...] = ("us",),
        timezones: tuple[str, ...] = ("UTC",),
        vendor: str | None = "GenuineIntel",
    ) -> None:
        self._l, self._k, self._t, self._v = locales, keymaps, timezones, vendor

    def cpu_vendor(self) -> str | None:
        return self._v

    def supported_locales(self) -> tuple[str, ...]:
        return self._l

    def keymaps(self) -> tuple[str, ...]:
        return self._k

    def timezones(self) -> tuple[str, ...]:
        return self._t


class _Fw:
    def __init__(self, *, uefi: bool = True) -> None:
        self._u = uefi

    def is_uefi(self) -> bool:
        return self._u


class _Pac:
    def __init__(self, *, exists: bool = True, keyring: bool = True) -> None:
        self._e = exists
        self._k = keyring

    def package_exists(self, name: str) -> bool:
        del name
        return self._e

    def keyring_initialized(self) -> bool:
        return self._k


class _Identity:
    def __init__(self, *, root: bool = True) -> None:
        self._r = root

    def is_root(self) -> bool:
        return self._r


class _Iso:
    def __init__(self, *, arch: bool = True) -> None:
        self._a = arch

    def is_arch_iso(self) -> bool:
        return self._a


class _Net:
    def __init__(self, *, reachable: bool = True) -> None:
        self._r = reachable

    def internet_reachable(self, host: str) -> bool:
        del host
        return self._r


def _cfg() -> Config:
    return Config.model_validate(EXAMPLES["minimal-ext4"])


def _disks() -> tuple[Disk, ...]:
    return (Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),)


def _call(
    *,
    bd: _BD | None = None,
    env: _Env | None = None,
    fw: _Fw | None = None,
    pac: _Pac | None = None,
    identity: _Identity | None = None,
    iso: _Iso | None = None,
    net: _Net | None = None,
) -> EnvironmentReport:
    return preflight_environment(
        _cfg(),
        bd or _BD(_disks()),
        env or _Env(),
        fw or _Fw(),
        pac or _Pac(),
        identity or _Identity(),
        iso or _Iso(),
        net or _Net(),
    )


def test_preflight_passes_when_environment_is_good() -> None:
    report = _call()
    assert isinstance(report, EnvironmentReport)
    assert report.disks_found
    assert report.is_root is True
    assert report.is_arch_iso is True
    assert report.internet_reachable is True
    assert report.keyring_initialized is True
    assert report.mountpoints_seen == ()


def test_preflight_fails_when_not_root() -> None:
    with pytest.raises(EnvErr, match="root"):
        _call(identity=_Identity(root=False))


def test_preflight_fails_when_not_arch_iso() -> None:
    with pytest.raises(EnvErr, match="Arch"):
        _call(iso=_Iso(arch=False))


def test_preflight_fails_when_no_internet() -> None:
    with pytest.raises(EnvErr, match="internet"):
        _call(net=_Net(reachable=False))


def test_preflight_fails_when_keyring_missing() -> None:
    with pytest.raises(EnvErr, match="keyring"):
        _call(pac=_Pac(keyring=False))


def test_preflight_fails_when_target_disk_busy() -> None:
    bd = _BD(_disks(), mounts=("/", "/boot"))
    with pytest.raises(EnvErr, match="mounted"):
        _call(bd=bd)


def test_preflight_fails_when_not_uefi() -> None:
    with pytest.raises(EnvErr, match="UEFI"):
        _call(fw=_Fw(uefi=False))


def test_preflight_fails_when_disk_missing() -> None:
    with pytest.raises(EnvErr, match="/dev/sda"):
        _call(bd=_BD(()))


def test_preflight_fails_when_locale_unsupported() -> None:
    with pytest.raises(EnvErr, match="locale"):
        _call(env=_Env(locales=("fr_FR.UTF-8 UTF-8",)))


def test_preflight_fails_when_package_missing() -> None:
    with pytest.raises(EnvErr, match="package"):
        _call(pac=_Pac(exists=False))


def test_preflight_fails_when_detached_luks_header_missing() -> None:
    cfg_dict = dict(EXAMPLES["minimal-ext4"])
    cfg_dict["encryption"] = {
        "kind": "luks2",
        "password": "x",
        "header_path": "/no/such/header",
    }
    cfg_dict["initramfs"] = {
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
    }
    cfg = Config.model_validate(cfg_dict)
    with pytest.raises(EnvErr, match="detached LUKS header"):
        preflight_environment(
            cfg,
            _BD(_disks()),
            _Env(),
            _Fw(),
            _Pac(),
            _Identity(),
            _Iso(),
            _Net(),
        )


def test_preflight_fails_when_static_mirrorlist_missing() -> None:
    cfg_dict = dict(EXAMPLES["minimal-ext4"])
    cfg_dict["mirrors"] = {
        "strategy": "static",
        "static_path": "/no/such/file",
    }
    cfg = Config.model_validate(cfg_dict)
    with pytest.raises(EnvErr, match="static mirrorlist"):
        preflight_environment(
            cfg,
            _BD(_disks()),
            _Env(),
            _Fw(),
            _Pac(),
            _Identity(),
            _Iso(),
            _Net(),
        )
