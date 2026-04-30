"""Filesystem creation strategies (ext4, btrfs)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.domain.filesystem import FilesystemKind, FilesystemSpec
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class Ext4Strategy:
    spec: FilesystemSpec
    root_partition: str
    efi_partition: str
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        return (
            Command(
                argv=("mkfs.fat", "-F", "32", "-n", "EFI", self.efi_partition),
                description="create FAT32 EFI filesystem",
            ),
            Command(
                argv=("mkfs.ext4", "-F", "-L", self.spec.label, self.root_partition),
                description=f"create ext4 filesystem labeled {self.spec.label}",
            ),
            Command(
                argv=("mount", self.root_partition, str(self.mount_root)),
                description="mount root filesystem",
            ),
            Command(
                argv=("mkdir", "-p", str(self.mount_root / "boot")),
                description="create /boot mountpoint",
            ),
            Command(
                argv=("mount", self.efi_partition, str(self.mount_root / "boot")),
                description="mount EFI filesystem at /boot",
            ),
        )


@dataclass(frozen=True, slots=True)
class BtrfsStrategy:
    spec: FilesystemSpec
    root_partition: str
    efi_partition: str
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = [
            Command(
                argv=("mkfs.fat", "-F", "32", "-n", "EFI", self.efi_partition),
                description="create FAT32 EFI filesystem",
            ),
            Command(
                argv=("mkfs.btrfs", "-f", "-L", self.spec.label, self.root_partition),
                description="create btrfs filesystem",
            ),
            Command(
                argv=("mount", self.root_partition, str(self.mount_root)),
                description="mount btrfs root for subvolume creation",
            ),
        ]
        for sv in self.spec.subvolumes:
            cmds.append(
                Command(
                    argv=(
                        "btrfs",
                        "subvolume",
                        "create",
                        str(self.mount_root / sv.name),
                    ),
                    description=f"create subvolume {sv.name}",
                ),
            )
        cmds.append(
            Command(
                argv=("umount", str(self.mount_root)),
                description="unmount before remount with subvolumes",
            ),
        )
        opts = ",".join(self.spec.mount_options) if self.spec.mount_options else "defaults"
        for sv in self.spec.subvolumes:
            target = (
                self.mount_root
                if sv.mountpoint == Path("/")
                else (self.mount_root / sv.mountpoint.relative_to("/"))
            )
            cmds.append(
                Command(
                    argv=("mkdir", "-p", str(target)),
                    description=f"ensure {target} exists",
                ),
            )
            cmds.append(
                Command(
                    argv=(
                        "mount",
                        "-o",
                        f"{opts},subvol={sv.name}",
                        self.root_partition,
                        str(target),
                    ),
                    description=f"mount subvolume {sv.name} at {target}",
                ),
            )
        cmds.append(
            Command(
                argv=("mkdir", "-p", str(self.mount_root / "boot")),
                description="create /boot mountpoint",
            ),
        )
        cmds.append(
            Command(
                argv=("mount", self.efi_partition, str(self.mount_root / "boot")),
                description="mount EFI at /boot",
            ),
        )
        return tuple(cmds)


def build_filesystem_strategy(
    spec: FilesystemSpec,
    *,
    root_partition: str,
    efi_partition: str,
    mount_root: Path,
) -> Ext4Strategy | BtrfsStrategy:
    if spec.kind is FilesystemKind.EXT4:
        return Ext4Strategy(spec, root_partition, efi_partition, mount_root)
    return BtrfsStrategy(spec, root_partition, efi_partition, mount_root)
