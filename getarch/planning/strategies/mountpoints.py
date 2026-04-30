"""Custom mountpoints strategy.

Each entry references an *existing* partition by partlabel. The strategy
formats the partition (when ``create=True``), creates the mountpoint inside
``mount_root``, and mounts the partition.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class MountpointPlan:
    partition_label: str
    mountpoint: str
    filesystem: str
    mount_options: tuple[str, ...]
    create: bool


@dataclass(frozen=True, slots=True)
class MountpointsStrategy:
    plans: tuple[MountpointPlan, ...]
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = []
        for plan in self.plans:
            partition_path = f"/dev/disk/by-partlabel/{plan.partition_label}"
            target = self.mount_root / plan.mountpoint.lstrip("/")
            if plan.create:
                cmds.append(
                    Command(
                        argv=_mkfs_argv(plan.filesystem, plan.partition_label, partition_path),
                        description=(
                            f"create {plan.filesystem} filesystem on "
                            f"{plan.partition_label} for {plan.mountpoint}"
                        ),
                    ),
                )
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


def _mkfs_argv(filesystem: str, label: str, partition_path: str) -> tuple[str, ...]:
    if filesystem == "ext4":
        return ("mkfs.ext4", "-F", "-L", label, partition_path)
    if filesystem == "btrfs":
        return ("mkfs.btrfs", "-f", "-L", label, partition_path)
    if filesystem == "xfs":
        return ("mkfs.xfs", "-f", "-L", label, partition_path)
    if filesystem == "f2fs":
        return ("mkfs.f2fs", "-f", "-L", label, partition_path)
    raise ValueError(f"unsupported filesystem for custom mountpoint: {filesystem!r}")
