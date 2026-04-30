"""Custom mountpoints strategy.

Each entry references an *existing* partition (by partlabel) on a disk
other than the install target. The strategy creates the mountpoint inside
``mount_root`` and mounts the partition. It does NOT format anything: that
would risk wiping data the user expects to keep.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class MountpointPlan:
    partition_label: str
    mountpoint: str
    mount_options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MountpointsStrategy:
    plans: tuple[MountpointPlan, ...]
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = []
        for plan in self.plans:
            partition_path = f"/dev/disk/by-partlabel/{plan.partition_label}"
            target = self.mount_root / plan.mountpoint.lstrip("/")
            cmds.append(
                Command(
                    argv=("mkdir", "-p", str(target)),
                    description=f"create {target} mountpoint",
                ),
            )
            mount_argv: list[str] = ["mount"]
            if plan.mount_options:
                mount_argv.extend(("-o", ",".join(plan.mount_options)))
            mount_argv.extend((partition_path, str(target)))
            cmds.append(
                Command(
                    argv=tuple(mount_argv),
                    description=f"mount {plan.partition_label} at {target}",
                ),
            )
        return tuple(cmds)
