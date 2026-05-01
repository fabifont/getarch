"""Exception hierarchy for getarch.

All public exceptions inherit from :class:`GetarchError`. Callers can
``except GetarchError`` to catch anything raised by this package without
catching unrelated runtime errors.

Each subclass declares a stable ``code`` (e.g. ``"E102"``). The CLI
exception handler prepends the code to every rendered message so users
can look up ``getarch help error <code>`` for actionable docs.
"""

from __future__ import annotations

from typing import ClassVar


class GetarchError(RuntimeError):
    """Base class for every error raised by getarch."""

    code: ClassVar[str] = "E000"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint: str | None = hint


class ConfigError(GetarchError):
    """Configuration is invalid."""

    code: ClassVar[str] = "E100"


class SyntacticConfigError(ConfigError):
    """Configuration cannot be parsed into the schema."""

    code: ClassVar[str] = "E101"


class SemanticConfigError(ConfigError):
    """Configuration parses but violates cross-field rules."""

    code: ClassVar[str] = "E102"


class EnvironmentError(GetarchError):  # noqa: A001 - domain term, not built-in shadow
    """Runtime environment cannot satisfy the install (missing tools, wrong mode)."""

    code: ClassVar[str] = "E200"


class DiscoveryError(GetarchError):
    """System discovery failed (lsblk, hostnamectl, etc.)."""

    code: ClassVar[str] = "E201"


class PlanError(GetarchError):
    """Install plan could not be built."""

    code: ClassVar[str] = "E300"


class CommandFailedError(GetarchError):
    """A command run by the executor returned a non-zero exit code."""

    __slots__ = ("argv", "returncode", "stderr")

    code: ClassVar[str] = "E400"

    def __init__(
        self,
        *,
        argv: tuple[str, ...],
        returncode: int,
        stderr: str = "",
        hint: str | None = None,
    ) -> None:
        self.argv: tuple[str, ...] = argv
        self.returncode: int = returncode
        self.stderr: str = stderr
        super().__init__(self._format_message(), hint=hint)

    def _format_message(self) -> str:
        rendered = " ".join(self.argv)
        return f"command {rendered!r} exited {self.returncode}: {self.stderr.strip()}"


# Public registry of every code → docs slug. The `help error <code>`
# CLI command consults this; tests assert there's a matching markdown
# stub under docs/errors/<code>.md for each entry.
ERROR_CODES: tuple[str, ...] = (
    "E000",
    "E100",
    "E101",
    "E102",
    "E200",
    "E201",
    "E300",
    "E400",
)
