"""Real CommandRunner - wraps :func:`subprocess.run` without ``shell=True``."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.result import CommandResult
from getarch.logging import get_logger, redact_secret

_log = get_logger(__name__)


@dataclass(slots=True)
class RealRunner:
    """Executes Commands via subprocess. Never uses ``shell=True``."""

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        argv = list(command.render(chroot_path=chroot_path))
        if command.sensitive:
            _log.debug("running (sensitive) %s", command.describe())
        else:
            _log.debug("running %s", " ".join(argv))

        completed = subprocess.run(  # noqa: S603 - explicit argv list, shell disabled
            argv,
            input=command.input,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
            timeout=command.timeout_seconds,
        )
        result = CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
        if command.check and not result.ok:
            stderr = (
                redact_secret(result.stderr, command.input) if command.sensitive else result.stderr
            )
            raise CommandFailedError(
                argv=command.argv,
                returncode=result.returncode,
                stderr=stderr,
            )
        return result
