"""Structured representation of a shell command.

Commands are pure data - they do not run anything by themselves. A
:class:`CommandRunner` turns them into actual subprocess calls (or fakes them
out in tests).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Command:
    """A command to execute through a CommandRunner.

    Attributes:
        argv: Tokens of the command. Never built by string concatenation.
        chroot: If True, the runner prepends ``arch-chroot <root>``.
        check: If True, a non-zero exit becomes :class:`CommandFailedError`.
        input: Optional stdin payload (passwords, EOF-fed scripts).
        sensitive: If True, ``argv`` and ``input`` are redacted in logs and
            :meth:`describe`.
        description: Human-readable purpose for plan rendering.
        timeout_seconds: Optional timeout passed through to the runner.
    """

    argv: tuple[str, ...]
    chroot: bool = False
    check: bool = True
    input: str | None = None
    sensitive: bool = False
    description: str | None = None
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("Command.argv must not be empty")

    def render(self, *, chroot_path: str) -> tuple[str, ...]:
        """Build the final argv that the runner passes to subprocess."""
        if self.chroot:
            return ("arch-chroot", chroot_path, *self.argv)
        return self.argv

    def describe(self) -> str:
        """Single-line description for logs and plan output. Never leaks secrets."""
        if self.sensitive:
            head = self.argv[0]
            return f"{head} <redacted>"
        return " ".join(self.argv)
