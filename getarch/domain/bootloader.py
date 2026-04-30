"""Bootloader value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BootloaderKind(StrEnum):
    SYSTEMD_BOOT = "systemd-boot"


@dataclass(frozen=True, slots=True)
class BootloaderSpec:
    kind: BootloaderKind = BootloaderKind.SYSTEMD_BOOT
    entry_id: str = "arch"
    timeout_seconds: int = 5
    extra_kernel_params: tuple[str, ...] = field(default_factory=tuple)
