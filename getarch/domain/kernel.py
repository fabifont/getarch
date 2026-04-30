"""Kernel and microcode value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KernelKind(StrEnum):
    LINUX = "linux"
    LTS = "linux-lts"
    ZEN = "linux-zen"
    HARDENED = "linux-hardened"


class MicrocodeKind(StrEnum):
    NONE = "none"
    INTEL = "intel"
    AMD = "amd"

    @property
    def package_name(self) -> str | None:
        match self:
            case MicrocodeKind.INTEL:
                return "intel-ucode"
            case MicrocodeKind.AMD:
                return "amd-ucode"
            case MicrocodeKind.NONE:
                return None


@dataclass(frozen=True, slots=True)
class KernelSpec:
    kind: KernelKind = KernelKind.LINUX

    @property
    def package_name(self) -> str:
        return self.kind.value

    @property
    def image_filename(self) -> str:
        return f"vmlinuz-{self.kind.value}"

    @property
    def initramfs_filename(self) -> str:
        return f"initramfs-{self.kind.value}.img"
