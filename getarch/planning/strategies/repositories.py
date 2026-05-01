"""Pacman repository configuration: multilib toggle + extra repos.

Operates on the *live ISO's* ``/etc/pacman.conf`` so ``pacstrap`` sees the
new repos. Pacstrap then copies the mirrorlist plus the activated repo
blocks into the new system. The strategy uses ``sed -i`` for the multilib
uncomment dance and ``install -Dm644`` heredoc-equivalents to append
extras; nothing here is destructive on the target disk.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class RepositoryEntry:
    name: str
    include: str


@dataclass(frozen=True, slots=True)
class RepositoriesStrategy:
    multilib: bool
    extras: tuple[RepositoryEntry, ...]

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = []
        if self.multilib:
            cmds.append(
                Command(
                    argv=(
                        "sed",
                        "-i",
                        # Uncomment the [multilib] header and the
                        # following Include line in one shot.
                        "/^#\\[multilib\\]$/,/^#Include/{s/^#//}",
                        "/etc/pacman.conf",
                    ),
                    description="enable [multilib] in /etc/pacman.conf",
                ),
            )
        cmds.extend(self._extra_commands())
        if cmds:
            cmds.append(
                Command(
                    argv=("pacman", "-Sy", "--noconfirm"),
                    description="refresh pacman db with new repos",
                ),
            )
        return tuple(cmds)

    def _extra_commands(self) -> Iterable[Command]:
        for entry in self.extras:
            block = f"\n[{entry.name}]\nInclude = {entry.include}\n"
            yield Command(
                argv=(
                    "sh",
                    "-c",
                    f"printf '%s' {_shell_quote(block)} >> /etc/pacman.conf",
                ),
                description=f"append [{entry.name}] to /etc/pacman.conf",
            )


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"
