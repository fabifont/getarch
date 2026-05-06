"""Swap strategies (swapfile, zram).

Swapfile: per Arch Wiki, btrfs CoW must be disabled on the directory
holding the swapfile *before* the file exists. Order: ``mkdir``,
``chattr +C`` (btrfs only), ``fallocate``, ``chmod``, ``mkswap``,
``swapon``. ``genfstab`` picks up the swapon entry from ``/proc/swaps``
so no explicit fstab append is needed.

zram: we don't activate anything during install. The strategy just installs
``zram-generator`` and writes ``/etc/systemd/zram-generator.conf``; the
target system mounts ``/dev/zram0`` automatically on first boot.
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


@dataclass(frozen=True, slots=True)
class ZramStrategy:
    mount_root: Path
    size_mib: int | None = None  # None → "min(ram, 8192)" idiom

    def commands(self) -> tuple[Command, ...]:
        conf_path = self.mount_root / "etc/systemd/zram-generator.conf"
        size_value = f"{self.size_mib}MiB" if self.size_mib is not None else "min(ram, 8192)"
        conf_text = f"[zram0]\nzram-size = {size_value}\ncompression-algorithm = zstd\n"
        return (
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(conf_path)),
                input=conf_text,
                description=f"write {conf_path}",
            ),
        )
