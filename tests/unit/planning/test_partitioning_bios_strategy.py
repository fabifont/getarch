from pathlib import Path

from getarch.config.schema.v1 import PartitionLayout
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.strategies.partitioning_bios import SgdiskBiosStrategy


def _disk() -> Disk:
    return Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33)


def test_bios_layout_starts_with_biosboot_partition() -> None:
    cmds = SgdiskBiosStrategy(
        disk=_disk(),
        layout=PartitionLayout(layout="efi-root", efi_size_mib=512),
        encrypted=False,
    ).commands()
    argvs = [c.argv for c in cmds]
    # First three sgdisk commands should target partition 1 with code ef02.
    assert argvs[0] == ("sgdisk", "--zap-all", "/dev/sda")
    assert any("--typecode=1:ef02" in a for a in argvs[1:4])
    assert any("--change-name=1:BIOSBOOT" in a for a in argvs[1:4])


def test_bios_encrypted_root_label_is_cryptsystem() -> None:
    cmds = SgdiskBiosStrategy(
        disk=_disk(),
        layout=PartitionLayout(layout="efi-root", efi_size_mib=512),
        encrypted=True,
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "cryptsystem" in flat
    assert "BIOSBOOT" in flat
