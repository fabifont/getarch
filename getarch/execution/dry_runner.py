"""DryRunner - records the commands the planner would run, executes nothing."""

from __future__ import annotations

from dataclasses import dataclass, field

from getarch.execution.command import Command
from getarch.execution.result import CommandResult


@dataclass(slots=True)
class DryRunner:
    """A CommandRunner that records intent but performs no IO."""

    recorded: list[Command] = field(default_factory=list)
    rendered: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        self.recorded.append(command)
        self.rendered.append(command.render(chroot_path=chroot_path))
        return CommandResult(command=command, returncode=0, stdout="", stderr="")
