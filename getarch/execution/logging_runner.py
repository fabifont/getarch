"""Decorator runner that records every command into an in-memory audit log.

The buffer is rendered as JSON lines. Sensitive commands have their argv
shortened to the binary name and their input redacted to ``"***"``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from getarch.execution.command import Command
from getarch.execution.result import CommandResult
from getarch.execution.runner import CommandRunner

_STDERR_TAIL_BYTES = 512


@dataclass(slots=True)
class LoggingRunner:
    inner: CommandRunner
    lines: list[str] = field(default_factory=list)

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        result = self.inner.run(command, chroot_path=chroot_path)
        self.lines.append(self._render(command, result, chroot_path))
        return result

    def render(self) -> str:
        """Return the audit log as a single string with a trailing newline."""
        return "".join(line + "\n" for line in self.lines)

    @staticmethod
    def _render(command: Command, result: CommandResult, chroot_path: str) -> str:
        argv = (
            (command.argv[0], "<redacted>") if command.sensitive else command.argv
        )
        record = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "argv": list(argv),
            "chroot": chroot_path if command.chroot else None,
            "exit": result.returncode,
            "stderr_tail": _tail(result.stderr),
            "input": "***" if command.sensitive and command.input else None,
        }
        return json.dumps(record, ensure_ascii=False, sort_keys=True)


def _tail(s: str) -> str:
    if len(s) <= _STDERR_TAIL_BYTES:
        return s
    return s[-_STDERR_TAIL_BYTES:]
