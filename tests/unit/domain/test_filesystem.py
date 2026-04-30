from pathlib import Path

import pytest

from getarch.domain.filesystem import (
    BtrfsSubvolume,
    FilesystemKind,
    FilesystemSpec,
    SwapKind,
)


def test_filesystemkind_values() -> None:
    assert FilesystemKind("ext4") is FilesystemKind.EXT4
    assert FilesystemKind("btrfs") is FilesystemKind.BTRFS


def test_btrfs_spec_carries_subvolumes() -> None:
    fs = FilesystemSpec(
        kind=FilesystemKind.BTRFS,
        label="system",
        mount_options=("compress=zstd", "noatime"),
        subvolumes=(
            BtrfsSubvolume(name="@", mountpoint=Path("/")),
            BtrfsSubvolume(name="@home", mountpoint=Path("/home")),
        ),
    )
    assert fs.subvolumes[0].name == "@"


def test_ext4_spec_rejects_subvolumes() -> None:
    with pytest.raises(ValueError, match="subvolumes"):
        FilesystemSpec(
            kind=FilesystemKind.EXT4,
            label="system",
            subvolumes=(BtrfsSubvolume(name="@", mountpoint=Path("/")),),
        )


def test_swapkind_values() -> None:
    assert SwapKind("none") is SwapKind.NONE
    assert SwapKind("partition") is SwapKind.PARTITION
    assert SwapKind("swapfile") is SwapKind.SWAPFILE
