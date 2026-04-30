"""Exception hierarchy for getarch.

All public exceptions inherit from :class:`GetarchError`. Callers can
``except GetarchError`` to catch anything raised by this package without
catching unrelated runtime errors.
"""

from __future__ import annotations


class GetarchError(RuntimeError):
    """Base class for every error raised by getarch."""


class ConfigError(GetarchError):
    """Configuration is invalid."""


class SyntacticConfigError(ConfigError):
    """Configuration cannot be parsed into the schema."""


class SemanticConfigError(ConfigError):
    """Configuration parses but violates cross-field rules."""


class EnvironmentError(GetarchError):  # noqa: A001 - domain term, not built-in shadow
    """Runtime environment cannot satisfy the install (missing tools, wrong mode)."""


class DiscoveryError(GetarchError):
    """System discovery failed (lsblk, hostnamectl, etc.)."""


class PlanError(GetarchError):
    """Install plan could not be built."""


class CommandFailedError(GetarchError):
    """A command run by the executor returned a non-zero exit code."""

    __slots__ = ("argv", "returncode", "stderr")

    def __init__(
        self,
        *,
        argv: tuple[str, ...],
        returncode: int,
        stderr: str = "",
    ) -> None:
        self.argv: tuple[str, ...] = argv
        self.returncode: int = returncode
        self.stderr: str = stderr
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        rendered = " ".join(self.argv)
        return f"command {rendered!r} exited {self.returncode}: {self.stderr.strip()}"
