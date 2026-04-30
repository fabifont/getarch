from pathlib import Path

from getarch.domain.filesystem import (
    BtrfsSubvolume,
    FilesystemKind,
    FilesystemSpec,
)
from getarch.planning.strategies.filesystem import (
    BtrfsStrategy,
    Ext4Strategy,
    build_filesystem_strategy,
)


def test_ext4_emits_mkfs_and_mount() -> None:
    spec = FilesystemSpec(kind=FilesystemKind.EXT4, label="system")
    cmds = build_filesystem_strategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
    ).commands()
    flat = [c.argv for c in cmds]
    assert ("mkfs.ext4", "-F", "-L", "system", "/dev/disk/by-partlabel/system") in flat
    assert any("mount" in c.argv[0] for c in cmds)


def test_btrfs_creates_subvolumes() -> None:
    spec = FilesystemSpec(
        kind=FilesystemKind.BTRFS,
        label="system",
        mount_options=("compress=zstd", "noatime"),
        subvolumes=(
            BtrfsSubvolume(name="@", mountpoint=Path("/")),
            BtrfsSubvolume(name="@home", mountpoint=Path("/home")),
            BtrfsSubvolume(name="@snapshots", mountpoint=Path("/.snapshots")),
        ),
    )
    cmds = build_filesystem_strategy(
        spec=spec,
        root_partition="/dev/mapper/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "mkfs.btrfs" in flat
    assert "subvol=@" in flat


def test_efi_mount_always_emitted() -> None:
    spec = FilesystemSpec(kind=FilesystemKind.EXT4, label="system")
    cmds = build_filesystem_strategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
    ).commands()
    rendered = " ".join(arg for c in cmds for arg in c.argv)
    assert "/mnt/boot" in rendered


def test_ext4_with_home_partition_creates_and_mounts_it() -> None:
    spec = FilesystemSpec(kind=FilesystemKind.EXT4, label="system")
    strat = Ext4Strategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
        home_partition="/dev/disk/by-partlabel/home",
    )
    argvs = [c.argv for c in strat.commands()]
    assert ("mkfs.ext4", "-F", "-L", "home", "/dev/disk/by-partlabel/home") in argvs
    assert ("mkdir", "-p", "/mnt/home") in argvs
    assert ("mount", "/dev/disk/by-partlabel/home", "/mnt/home") in argvs


def test_xfs_strategy_emits_mkfs_xfs() -> None:
    spec = FilesystemSpec(kind=FilesystemKind.XFS, label="system")
    cmds = build_filesystem_strategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
    ).commands()
    flat = [c.argv for c in cmds]
    assert ("mkfs.xfs", "-f", "-L", "system", "/dev/disk/by-partlabel/system") in flat


def test_f2fs_strategy_emits_mkfs_f2fs() -> None:
    spec = FilesystemSpec(kind=FilesystemKind.F2FS, label="system")
    cmds = build_filesystem_strategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
    ).commands()
    flat = [c.argv for c in cmds]
    # f2fs uses lowercase -l for label.
    assert ("mkfs.f2fs", "-f", "-l", "system", "/dev/disk/by-partlabel/system") in flat


def test_btrfs_with_home_partition_creates_separate_filesystem() -> None:
    spec = FilesystemSpec(
        kind=FilesystemKind.BTRFS,
        label="system",
        subvolumes=(
            BtrfsSubvolume(name="@", mountpoint=Path("/")),
            BtrfsSubvolume(name="@snapshots", mountpoint=Path("/.snapshots")),
        ),
    )
    strat = BtrfsStrategy(
        spec=spec,
        root_partition="/dev/disk/by-partlabel/system",
        efi_partition="/dev/disk/by-partlabel/EFI",
        mount_root=Path("/mnt"),
        home_partition="/dev/disk/by-partlabel/home",
    )
    argvs = [c.argv for c in strat.commands()]
    assert ("mkfs.btrfs", "-f", "-L", "home", "/dev/disk/by-partlabel/home") in argvs
    assert ("mount", "/dev/disk/by-partlabel/home", "/mnt/home") in argvs
