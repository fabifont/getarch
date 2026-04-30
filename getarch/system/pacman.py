"""Pacman wrapper used for package validation and keyring presence checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from getarch.constants import PACMAN_KEYRING_PATH
from getarch.execution.command import Command
from getarch.execution.runner import CommandRunner

_PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z0-9@._+\-]+$")


@dataclass(slots=True)
class Pacman:
    runner: CommandRunner
    keyring_path: Path = field(default=PACMAN_KEYRING_PATH)

    def package_exists(self, name: str) -> bool:
        if not _PACKAGE_NAME_RE.match(name):
            raise ValueError(f"invalid package name: {name!r}")
        result = self.runner.run(Command(argv=("pacman", "-Si", name), check=False))
        return result.ok

    def keyring_initialized(self) -> bool:
        try:
            return self.keyring_path.is_file() and self.keyring_path.stat().st_size > 0
        except OSError:
            return False
