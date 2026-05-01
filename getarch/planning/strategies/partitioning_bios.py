"""BIOS/MBR partitioning via sgdisk (still GPT, with a 1MiB BIOS-boot
partition for grub-bios stage 1.5).

Pure GPT-on-BIOS layout (a.k.a. GPT-MBR hybrid) avoids the legacy MS-DOS
partition table limits while still booting through GRUB on a non-UEFI
host. The first partition is a 1MiB ``EF02`` partition (BIOS boot) that
holds GRUB stage 1.5; the remaining layout mirrors :class:`SgdiskStrategy`
without the EFI System Partition.
"""

from __future__ import annotations

from dataclasses import dataclass

from getarch.config.schema.v1 import PartitionLayout
from getarch.domain.disk import Disk
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SgdiskBiosStrategy:
    disk: Disk
    layout: PartitionLayout
    encrypted: bool

    def commands(self) -> tuple[Command, ...]:
        path = self.disk.path.as_posix()
        cmds: list[Command] = [
            Command(
                argv=("sgdisk", "--zap-all", path),
                description="wipe partition table",
            ),
        ]
        index = 1
        # 1MiB BIOS boot partition, no filesystem.
        cmds.extend(self._partition(index, "+1MiB", "ef02", "BIOSBOOT"))
        index += 1

        if "swap" in self.layout.layout:
            size = self.layout.swap_size_mib or 2048
            cmds.extend(self._partition(index, f"+{size}MiB", "8200", "swap"))
            index += 1

        root_label = "cryptsystem" if self.encrypted else "system"
        if "home" in self.layout.layout:
            home_size = self.layout.home_size_mib
            root_size = self.layout.root_size_mib
            if home_size is not None:
                cmds.extend(
                    self._partition(index, f"+{home_size}MiB", "8302", "home"),
                )
                index += 1
                cmds.extend(self._partition(index, "0", "8300", root_label))
            elif root_size is not None:
                cmds.extend(
                    self._partition(index, f"+{root_size}MiB", "8300", root_label),
                )
                index += 1
                cmds.extend(self._partition(index, "0", "8302", "home"))
            else:
                raise ValueError(
                    "home layout requires either home_size_mib or root_size_mib",
                )
            return tuple(cmds)

        cmds.extend(self._partition(index, "0", "8300", root_label))
        return tuple(cmds)

    def _partition(self, idx: int, end: str, code: str, label: str) -> tuple[Command, ...]:
        path = self.disk.path.as_posix()
        return (
            Command(
                argv=("sgdisk", f"--new={idx}:0:{end}", path),
                description=f"create partition {idx} ({label}, {code})",
            ),
            Command(
                argv=("sgdisk", f"--typecode={idx}:{code}", path),
                description=f"set partition {idx} type to {code}",
            ),
            Command(
                argv=("sgdisk", f"--change-name={idx}:{label}", path),
                description=f"label partition {idx} as {label}",
            ),
        )
