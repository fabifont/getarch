"""Filesystem value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class FilesystemKind(StrEnum):
    EXT4 = "ext4"
    BTRFS = "btrfs"
    XFS = "xfs"
    F2FS = "f2fs"


class SwapKind(StrEnum):
    NONE = "none"
    PARTITION = "partition"
    SWAPFILE = "swapfile"


@dataclass(frozen=True, slots=True)
class BtrfsSubvolume:
    name: str
    mountpoint: Path

    def __post_init__(self) -> None:
        if not self.name.startswith("@"):
            raise ValueError("btrfs subvolume names must start with '@'")
        if not self.mountpoint.is_absolute():
            raise ValueError("btrfs subvolume mountpoint must be absolute")


@dataclass(frozen=True, slots=True)
class FilesystemSpec:
    kind: FilesystemKind
    label: str
    mount_options: tuple[str, ...] = field(default_factory=tuple)
    subvolumes: tuple[BtrfsSubvolume, ...] = field(default_factory=tuple)
    home_label: str = "home"

    def __post_init__(self) -> None:
        if self.subvolumes and self.kind is not FilesystemKind.BTRFS:
            raise ValueError("subvolumes only valid for btrfs")
