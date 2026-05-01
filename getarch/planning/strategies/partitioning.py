"""GPT partitioning via sgdisk."""

from __future__ import annotations

from dataclasses import dataclass

from getarch.config.schema.v1 import PartitionLayout
from getarch.domain.disk import Disk
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SgdiskStrategy:
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
        cmds.extend(self._partition(index, f"+{self.layout.efi_size_mib}MiB", "ef00", "EFI"))
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
                # Original layout: home is fixed, root takes the rest.
                cmds.extend(
                    self._partition(index, f"+{home_size}MiB", "8302", "home"),
                )
                index += 1
                cmds.extend(self._partition(index, "0", "8300", root_label))
            elif root_size is not None:
                # Reverse layout: root is fixed, home takes the rest.
                cmds.extend(
                    self._partition(index, f"+{root_size}MiB", "8300", root_label),
                )
                index += 1
                cmds.extend(self._partition(index, "0", "8302", "home"))
            else:
                # Validator should have caught this; guard anyway.
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
