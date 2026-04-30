"""Pacman wrapper used for package validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from getarch.execution.command import Command
from getarch.execution.runner import CommandRunner

_PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z0-9@._+\-]+$")


@dataclass(slots=True)
class Pacman:
    runner: CommandRunner

    def package_exists(self, name: str) -> bool:
        if not _PACKAGE_NAME_RE.match(name):
            raise ValueError(f"invalid package name: {name!r}")
        result = self.runner.run(Command(argv=("pacman", "-Si", name), check=False))
        return result.ok
