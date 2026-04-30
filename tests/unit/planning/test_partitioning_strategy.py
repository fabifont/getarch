from pathlib import Path

from getarch.config.schema.v1 import PartitionLayout
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.strategies.partitioning import SgdiskStrategy


def test_efi_root_layout_emits_two_partitions() -> None:
    disk = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)
    layout = PartitionLayout(layout="efi-root", efi_size_mib=512)
    cmds = SgdiskStrategy(disk=disk, layout=layout, encrypted=False).commands()
    rendered = [c.argv for c in cmds]
    assert ("sgdisk", "--zap-all", "/dev/sda") in rendered
    assert any("--new=1:0:+512MiB" in arg for cmd in rendered for arg in cmd)
    assert any("ef00" in arg for cmd in rendered for arg in cmd)
    assert any("8300" in arg for cmd in rendered for arg in cmd)


def test_encrypted_uses_cryptsystem_label() -> None:
    disk = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)
    layout = PartitionLayout(layout="efi-root", efi_size_mib=512)
    cmds = SgdiskStrategy(disk=disk, layout=layout, encrypted=True).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "cryptsystem" in flat


def test_efi_swap_root_three_partitions() -> None:
    disk = Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)
    layout = PartitionLayout(layout="efi-swap-root", efi_size_mib=512, swap_size_mib=2048)
    cmds = SgdiskStrategy(disk=disk, layout=layout, encrypted=False).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "8200" in flat
    assert "+2048MiB" in flat
