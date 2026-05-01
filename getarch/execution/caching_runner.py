"""CommandRunner decorator that caches stdout for idempotent reads.

Wraps another :class:`CommandRunner`. When a command's argv starts with
one of :attr:`CACHEABLE_PREFIXES` *and* its ``input`` is empty *and*
``sensitive`` is false, the runner consults a :class:`TimedCache` first
and skips the underlying invocation on a hit. Cache misses run the
command and store the resulting stdout, but only when the command
returned exit 0 (so we never replay a transient failure).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from getarch.execution.command import Command
from getarch.execution.result import CommandResult
from getarch.execution.runner import CommandRunner
from getarch.system.cache import TimedCache

# Whitelist of read-only discovery commands. Anything else passes
# straight through — we never want to cache writes.
CACHEABLE_PREFIXES: Final[tuple[tuple[str, ...], ...]] = (
    ("lsblk",),
    ("localectl",),
    ("timedatectl",),
    ("hostnamectl",),
    ("ip",),
    ("lspci",),
    ("lsusb",),
    ("efivar",),
    ("cat", "/etc/os-release"),
    ("cat", "/proc/cpuinfo"),
)


def _is_cacheable(command: Command) -> bool:
    if command.input or command.sensitive or command.chroot:
        return False
    argv = command.argv
    return any(
        len(prefix) <= len(argv) and argv[: len(prefix)] == prefix
        for prefix in CACHEABLE_PREFIXES
    )


@dataclass(slots=True)
class CachingRunner:
    inner: CommandRunner
    cache: TimedCache

    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        if not _is_cacheable(command):
            return self.inner.run(command, chroot_path=chroot_path)
        cached = self.cache.get(command.argv)
        if cached is not None:
            return CommandResult(
                command=command,
                returncode=0,
                stdout=cached,
                stderr="",
            )
        result = self.inner.run(command, chroot_path=chroot_path)
        if result.ok:
            self.cache.put(command.argv, result.stdout)
        return result
