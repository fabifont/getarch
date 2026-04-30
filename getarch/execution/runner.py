"""The CommandRunner protocol - every executor depends only on this surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from getarch.execution.command import Command
from getarch.execution.result import CommandResult


@runtime_checkable
class CommandRunner(Protocol):
    """Anything that knows how to run a :class:`Command`."""

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult: ...
