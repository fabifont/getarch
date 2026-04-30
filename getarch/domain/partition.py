"""Partition value objects: roles, sizes, GPT type GUIDs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PartitionRole(StrEnum):
    EFI = "efi"
    ROOT = "root"
    SWAP = "swap"
    HOME = "home"


GPT_TYPE_CODES: dict[PartitionRole, str] = {
    PartitionRole.EFI: "ef00",
    PartitionRole.ROOT: "8300",
    PartitionRole.SWAP: "8200",
    PartitionRole.HOME: "8302",
}


@dataclass(frozen=True, slots=True)
class ByteSize:
    bytes: int

    def __post_init__(self) -> None:
        if self.bytes <= 0:
            raise ValueError("ByteSize must be positive")

    @classmethod
    def from_mib(cls, mib: int) -> ByteSize:
        return cls(bytes=mib * 1024 * 1024)

    @classmethod
    def from_gib(cls, gib: int) -> ByteSize:
        return cls(bytes=gib * 1024 * 1024 * 1024)

    @property
    def mib(self) -> int:
        return self.bytes // (1024 * 1024)


@dataclass(frozen=True, slots=True)
class PartitionSpec:
    role: PartitionRole
    size: ByteSize | None
    label: str | None = None

    def __post_init__(self) -> None:
        if self.role is PartitionRole.EFI and self.size is None:
            raise ValueError("EFI partition must have a fixed size")
