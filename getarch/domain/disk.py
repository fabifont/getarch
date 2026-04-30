"""Disk and DiskPath value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PARTITION_SUFFIX_RE = re.compile(r"(\d+|p\d+)$")
_NEEDS_P_PREFIX_RE = re.compile(r"(nvme\d+n\d+|mmcblk\d+|loop\d+|nbd\d+)$")


@dataclass(frozen=True, slots=True)
class DiskPath:
    path: Path

    def __post_init__(self) -> None:
        s = self.path.as_posix()
        if not s.startswith("/dev/"):
            raise ValueError(f"DiskPath must start with /dev/: {s}")
        name = self.path.name
        if _PARTITION_SUFFIX_RE.search(name) and _NEEDS_P_PREFIX_RE.search(name) is None:
            raise ValueError(f"DiskPath looks like a partition, not a whole disk: {s}")

    def as_posix(self) -> str:
        return self.path.as_posix()


@dataclass(frozen=True, slots=True)
class Disk:
    path: DiskPath
    size_bytes: int
    model: str | None = None

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("Disk.size_bytes must be > 0")

    def partition_path(self, index: int) -> Path:
        if index <= 0:
            raise ValueError("partition index must be >= 1")
        name = self.path.path.name
        suffix = f"p{index}" if _NEEDS_P_PREFIX_RE.search(name) else str(index)
        return self.path.path.with_name(f"{name}{suffix}")
