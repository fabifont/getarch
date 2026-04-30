from pathlib import Path

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.errors import EnvironmentError as EnvErr
from getarch.system.preflight import EnvironmentReport, preflight_environment


class _BD:
    def __init__(self, disks: tuple[Disk, ...]) -> None:
        self._d = disks

    def list_disks(self) -> tuple[Disk, ...]:
        return self._d


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
    def __init__(self, *, exists: bool = True) -> None:
        self._e = exists

    def package_exists(self, name: str) -> bool:
        del name
        return self._e


def _cfg() -> Config:
    return Config.model_validate(EXAMPLES["minimal-ext4"])


def test_preflight_passes_when_environment_is_good() -> None:
    cfg = _cfg()
    bd = _BD((Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),))
    env = _Env()
    report = preflight_environment(cfg, bd, env, _Fw(), _Pac())
    assert isinstance(report, EnvironmentReport)
    assert report.disks_found


def test_preflight_fails_when_not_uefi() -> None:
    cfg = _cfg()
    bd = _BD((Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),))
    with pytest.raises(EnvErr, match="UEFI"):
        preflight_environment(cfg, bd, _Env(), _Fw(uefi=False), _Pac())


def test_preflight_fails_when_disk_missing() -> None:
    cfg = _cfg()
    bd = _BD(())
    with pytest.raises(EnvErr, match="/dev/sda"):
        preflight_environment(cfg, bd, _Env(), _Fw(), _Pac())


def test_preflight_fails_when_locale_unsupported() -> None:
    cfg = _cfg()
    bd = _BD((Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),))
    env = _Env(locales=("fr_FR.UTF-8 UTF-8",))
    with pytest.raises(EnvErr, match="locale"):
        preflight_environment(cfg, bd, env, _Fw(), _Pac())


def test_preflight_fails_when_package_missing() -> None:
    cfg = _cfg()
    bd = _BD((Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),))
    with pytest.raises(EnvErr, match="package"):
        preflight_environment(cfg, bd, _Env(), _Fw(), _Pac(exists=False))
