"""InstallPlan and PlannedStep - the structured artifact emitted by the planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from getarch.execution.command import Command


class StepPhase(StrEnum):
    PREFLIGHT = "preflight"
    PARTITIONING = "partitioning"
    ENCRYPTION = "encryption"
    FILESYSTEMS = "filesystems"
    MOUNTING = "mounting"
    SWAP = "swap"
    MIRRORS = "mirrors"
    PACKAGES = "packages"
    FSTAB = "fstab"
    SYSTEM_CONFIG = "system-config"
    INITRAMFS = "initramfs"
    BOOTLOADER = "bootloader"
    SERVICES = "services"
    USERS = "users"
    CLEANUP = "cleanup"
    REBOOT = "reboot"


@dataclass(frozen=True, slots=True)
class PlannedStep:
    id: str
    title: str
    phase: StepPhase
    commands: tuple[Command, ...]
    destructive: bool
    description: str
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    rollback_hints: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.id or not self.title:
            raise ValueError("PlannedStep requires non-empty id and title")


@dataclass(frozen=True, slots=True)
class InstallPlan:
    version: str
    steps: tuple[PlannedStep, ...]

    def __post_init__(self) -> None:
        ids = [s.id for s in self.steps]
        if len(set(ids)) != len(ids):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate step ids: {duplicates}")

    @property
    def has_destructive_steps(self) -> bool:
        return any(s.destructive for s in self.steps)

    @property
    def destructive_steps(self) -> tuple[PlannedStep, ...]:
        return tuple(s for s in self.steps if s.destructive)
