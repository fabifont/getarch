"""Swapfile creation strategy.

Per Arch Wiki, btrfs CoW must be disabled on the directory holding the
swapfile *before* the file exists. Order: ``mkdir``, ``chattr +C`` (btrfs
only), ``fallocate``, ``chmod``, ``mkswap``, ``swapon``. ``genfstab`` picks
up the swapon entry from ``/proc/swaps`` so no explicit fstab append is
needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SwapfileStrategy:
    size_mib: int
    mount_root: Path
    btrfs: bool
    swap_dir: Path = Path("/swap")
    swapfile_name: str = "swapfile"

    def commands(self) -> tuple[Command, ...]:
        target_dir = self.mount_root / self.swap_dir.relative_to("/")
        target_file = target_dir / self.swapfile_name
        cmds: list[Command] = [
            Command(
                argv=("mkdir", "-p", str(target_dir)),
                description=f"create {target_dir}",
            ),
        ]
        if self.btrfs:
            cmds.append(
                Command(
                    argv=("chattr", "+C", str(target_dir)),
                    description=f"disable CoW on {target_dir} for btrfs swap",
                ),
            )
        cmds.extend(
            (
                Command(
                    argv=("fallocate", "-l", f"{self.size_mib}MiB", str(target_file)),
                    description=f"allocate {self.size_mib} MiB swapfile",
                ),
                Command(
                    argv=("chmod", "600", str(target_file)),
                    description="restrict swapfile permissions",
                ),
                Command(
                    argv=("mkswap", str(target_file)),
                    description="format swapfile",
                ),
                Command(
                    argv=("swapon", str(target_file)),
                    description="activate swapfile so genfstab records it",
                ),
            ),
        )
        return tuple(cmds)
