"""Custom GPT partitioning via sgdisk for user-declared layouts.

Each entry in :attr:`PartitionLayout.custom` becomes one set of sgdisk
commands (``--new``, ``--typecode``, ``--change-name``). Partitions
appear on the disk in the same order as the user listed them. The one
partition with ``size_mib=None`` (if any) consumes the rest of the disk
via ``sgdisk --new=N:0:0``.
"""

from __future__ import annotations

from dataclasses import dataclass

from getarch.config.schema.v1 import CustomPartition
from getarch.domain.disk import Disk
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SgdiskCustomStrategy:
    disk: Disk
    partitions: tuple[CustomPartition, ...]

    def commands(self) -> tuple[Command, ...]:
        path = self.disk.path.as_posix()
        cmds: list[Command] = [
            Command(
                argv=("sgdisk", "--zap-all", path),
                description="wipe partition table",
            ),
        ]
        for idx, p in enumerate(self.partitions, start=1):
            end = "0" if p.size_mib is None else f"+{p.size_mib}MiB"
            cmds.extend(
                (
                    Command(
                        argv=("sgdisk", f"--new={idx}:0:{end}", path),
                        description=(
                            f"create partition {idx} ({p.label}, {p.typecode}, "
                            f"role={p.role})"
                        ),
                    ),
                    Command(
                        argv=("sgdisk", f"--typecode={idx}:{p.typecode}", path),
                        description=f"set partition {idx} type to {p.typecode}",
                    ),
                    Command(
                        argv=("sgdisk", f"--change-name={idx}:{p.label}", path),
                        description=f"label partition {idx} as {p.label}",
                    ),
                ),
            )
        return tuple(cmds)


def role_to_label(partitions: tuple[CustomPartition, ...]) -> dict[str, str]:
    """Map every non-extra role to the corresponding partition label."""
    return {p.role: p.label for p in partitions if p.role != "extra"}
