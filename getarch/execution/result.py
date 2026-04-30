"""Result objects produced by the execution layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from getarch.execution.command import Command


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    DRY_RUN = "dry-run"


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: Command
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True, slots=True)
class StepResult:
    step_id: str
    status: StepStatus
    commands: tuple[CommandResult, ...] = field(default_factory=tuple)
    message: str | None = None
