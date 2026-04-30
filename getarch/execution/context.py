"""ExecutionContext - bundles the runner, mount root, and policy flags."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.runner import CommandRunner


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    runner: CommandRunner
    mount_root: Path
    assume_yes: bool = False
    force: bool = False
