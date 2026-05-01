"""snapper integration for btrfs root.

Runs after the new system is fully populated so ``snapper`` is available.
Creates a config for ``/`` and registers the timeline + cleanup timers via
the planner's normal services pipeline (the planner adds them when this
strategy is used).
"""

from __future__ import annotations

from dataclasses import dataclass

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SnapperStrategy:
    def commands(self) -> tuple[Command, ...]:
        return (
            Command(
                argv=("snapper", "--no-dbus", "-c", "root", "create-config", "/"),
                chroot=True,
                description="initialise snapper config for /",
            ),
        )
