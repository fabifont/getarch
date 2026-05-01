"""Decorator runner that records every command into an in-memory audit log.

The buffer is rendered as JSON lines (schema_version=1). Sensitive
commands have their argv shortened to the binary name and their input
redacted to ``"***"``.

When :attr:`hmac_key` is set, :meth:`render` appends a final
``{"schema_version": 1, "type": "hmac", "alg": "HMAC-SHA256",
"value": "<hex>"}`` line whose ``value`` covers the concatenation of
all prior records (including the trailing newline of each).

The schema is documented at ``docs/audit-schema.md``.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final

from getarch.execution.command import Command
from getarch.execution.result import CommandResult
from getarch.execution.runner import CommandRunner

_STDERR_TAIL_BYTES = 512
AUDIT_SCHEMA_VERSION: Final[int] = 1


@dataclass(slots=True)
class LoggingRunner:
    inner: CommandRunner
    lines: list[str] = field(default_factory=list)
    hmac_key: bytes | None = None

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        result = self.inner.run(command, chroot_path=chroot_path)
        self.lines.append(self._render(command, result, chroot_path))
        return result

    def render(self) -> str:
        """Return the audit log as a single string with a trailing newline.

        When ``hmac_key`` is set, an HMAC-SHA256 line is appended that
        covers the concatenation of all prior records (including their
        trailing newlines).
        """
        body = "".join(line + "\n" for line in self.lines)
        if self.hmac_key is None:
            return body
        digest = hmac.new(
            self.hmac_key, body.encode("utf-8"), sha256,
        ).hexdigest()
        trailer = json.dumps(
            {
                "schema_version": AUDIT_SCHEMA_VERSION,
                "type": "hmac",
                "alg": "HMAC-SHA256",
                "value": digest,
            },
            sort_keys=True,
        )
        return body + trailer + "\n"

    @staticmethod
    def _render(command: Command, result: CommandResult, chroot_path: str) -> str:
        argv = (
            (command.argv[0], "<redacted>") if command.sensitive else command.argv
        )
        record = {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "type": "command",
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
