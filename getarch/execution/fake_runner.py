"""In-memory CommandRunner for tests.

Unit tests across installers, planners, and the CLI inject :class:`FakeRunner`
so they never touch the host system.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.result import CommandResult


@dataclass(frozen=True, slots=True)
class FakeResponse:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(slots=True)
class FakeRunner:
    """Records every Command and returns canned responses keyed by argv tuple."""

    responses: dict[tuple[str, ...], FakeResponse] = field(default_factory=dict)
    default: FakeResponse = field(default_factory=FakeResponse)
    recorded: list[Command] = field(default_factory=list)
    rendered: list[tuple[str, ...]] = field(default_factory=list)

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        self.recorded.append(command)
        rendered_argv = command.render(chroot_path=chroot_path)
        self.rendered.append(rendered_argv)
        response = self._lookup(command.argv)
        result = CommandResult(
            command=command,
            returncode=response.returncode,
            stdout=response.stdout,
            stderr=response.stderr,
        )
        if command.check and not result.ok:
            raise CommandFailedError(
                argv=command.argv,
                returncode=response.returncode,
                stderr=response.stderr,
            )
        return result

    def _lookup(self, argv: tuple[str, ...]) -> FakeResponse:
        if argv in self.responses:
            return self.responses[argv]
        for length in range(len(argv) - 1, 0, -1):
            prefix = argv[:length]
            if prefix in self.responses:
                return self.responses[prefix]
        return self.default

    def reset(self) -> None:
        self.recorded.clear()
        self.rendered.clear()
