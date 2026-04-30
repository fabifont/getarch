from pathlib import Path

import pytest

from getarch.domain.disk import Disk, DiskPath


def test_diskpath_must_start_with_dev() -> None:
    with pytest.raises(ValueError, match="must start with /dev/"):
        DiskPath(Path("/sda"))


def test_diskpath_rejects_partition_suffix() -> None:
    with pytest.raises(ValueError, match="partition"):
        DiskPath(Path("/dev/sda1"))


def test_diskpath_accepts_whole_disk() -> None:
    p = DiskPath(Path("/dev/sda"))
    assert p.as_posix() == "/dev/sda"


def test_diskpath_accepts_nvme() -> None:
    p = DiskPath(Path("/dev/nvme0n1"))
    assert p.as_posix() == "/dev/nvme0n1"


def test_disk_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Disk(path=DiskPath(Path("/dev/sda")), size_bytes=0)


def test_disk_partition_path_for_nvme() -> None:
    d = Disk(path=DiskPath(Path("/dev/nvme0n1")), size_bytes=1_000_000_000)
    assert d.partition_path(1).as_posix() == "/dev/nvme0n1p1"


def test_disk_partition_path_for_sd() -> None:
    d = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=1_000_000_000)
    assert d.partition_path(2).as_posix() == "/dev/sda2"
