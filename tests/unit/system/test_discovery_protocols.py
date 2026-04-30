from pathlib import Path

from getarch.domain.disk import Disk, DiskPath
from getarch.system.discovery import (
    BlockDeviceProvider,
    EnvironmentProvider,
    FirmwareProvider,
    PacmanProvider,
)


class _BD:
    def list_disks(self) -> tuple[Disk, ...]:
        return (Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),)


class _Env:
    def cpu_vendor(self) -> str | None:
        return "GenuineIntel"

    def supported_locales(self) -> tuple[str, ...]:
        return ("en_US.UTF-8 UTF-8",)

    def keymaps(self) -> tuple[str, ...]:
        return ("us",)

    def timezones(self) -> tuple[str, ...]:
        return ("Europe/Rome",)


class _Fw:
    def is_uefi(self) -> bool:
        return True


class _Pac:
    def package_exists(self, name: str) -> bool:
        return name == "base"


def test_protocols_satisfied() -> None:
    bd: BlockDeviceProvider = _BD()
    env: EnvironmentProvider = _Env()
    fw: FirmwareProvider = _Fw()
    pac: PacmanProvider = _Pac()
    assert bd.list_disks()
    assert env.cpu_vendor() == "GenuineIntel"
    assert fw.is_uefi()
    assert pac.package_exists("base")
