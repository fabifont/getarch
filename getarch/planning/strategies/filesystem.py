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
    home_partition: str | None = None

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = [
            Command(
                argv=("mkfs.fat", "-F", "32", "-n", "EFI", self.efi_partition),
                description="create FAT32 EFI filesystem",
            ),
            Command(
                argv=("mkfs.ext4", "-F", "-L", self.spec.label, self.root_partition),
                description=f"create ext4 filesystem labeled {self.spec.label}",
            ),
        ]
        if self.home_partition:
            cmds.append(
                Command(
                    argv=(
                        "mkfs.ext4",
                        "-F",
                        "-L",
                        self.spec.home_label,
                        self.home_partition,
                    ),
                    description=(
                        f"create ext4 /home filesystem labeled {self.spec.home_label}"
                    ),
                ),
            )
        cmds.extend(
            (
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
            ),
        )
        if self.home_partition:
            cmds.extend(
                (
                    Command(
                        argv=("mkdir", "-p", str(self.mount_root / "home")),
                        description="create /home mountpoint",
                    ),
                    Command(
                        argv=("mount", self.home_partition, str(self.mount_root / "home")),
                        description="mount /home filesystem",
                    ),
                ),
            )
        return tuple(cmds)


@dataclass(frozen=True, slots=True)
class BtrfsStrategy:
    spec: FilesystemSpec
    root_partition: str
    efi_partition: str
    mount_root: Path
    home_partition: str | None = None

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = [
            Command(
                argv=("mkfs.fat", "-F", "32", "-n", "EFI", self.efi_partition),
                description="create FAT32 EFI filesystem",
            ),
            Command(
                argv=("mkfs.btrfs", "-f", "-L", self.spec.label, self.root_partition),
                description="create btrfs root filesystem",
            ),
        ]
        if self.home_partition:
            cmds.append(
                Command(
                    argv=(
                        "mkfs.btrfs",
                        "-f",
                        "-L",
                        self.spec.home_label,
                        self.home_partition,
                    ),
                    description=(
                        f"create btrfs /home filesystem labeled {self.spec.home_label}"
                    ),
                ),
            )
        cmds.append(
            Command(
                argv=("mount", self.root_partition, str(self.mount_root)),
                description="mount btrfs root for subvolume creation",
            ),
        )
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
        if self.home_partition:
            cmds.append(
                Command(
                    argv=("mkdir", "-p", str(self.mount_root / "home")),
                    description="create /home mountpoint",
                ),
            )
            cmds.append(
                Command(
                    argv=("mount", self.home_partition, str(self.mount_root / "home")),
                    description="mount /home filesystem",
                ),
            )
        return tuple(cmds)


@dataclass(frozen=True, slots=True)
class _SimpleMkfsStrategy:
    """Shared body for ext4/xfs/f2fs (no subvolumes)."""

    spec: FilesystemSpec
    root_partition: str
    efi_partition: str
    mount_root: Path
    home_partition: str | None
    mkfs_argv: tuple[str, ...]
    description_label: str

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = [
            Command(
                argv=("mkfs.fat", "-F", "32", "-n", "EFI", self.efi_partition),
                description="create FAT32 EFI filesystem",
            ),
            Command(
                argv=(*self.mkfs_argv, "-L", self.spec.label, self.root_partition),
                description=(
                    f"create {self.description_label} filesystem labeled {self.spec.label}"
                ),
            ),
        ]
        if self.home_partition:
            cmds.append(
                Command(
                    argv=(
                        *self.mkfs_argv,
                        "-L",
                        self.spec.home_label,
                        self.home_partition,
                    ),
                    description=(
                        f"create {self.description_label} /home filesystem "
                        f"labeled {self.spec.home_label}"
                    ),
                ),
            )
        cmds.extend(
            (
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
            ),
        )
        if self.home_partition:
            cmds.extend(
                (
                    Command(
                        argv=("mkdir", "-p", str(self.mount_root / "home")),
                        description="create /home mountpoint",
                    ),
                    Command(
                        argv=("mount", self.home_partition, str(self.mount_root / "home")),
                        description="mount /home filesystem",
                    ),
                ),
            )
        return tuple(cmds)


def _xfs_strategy(
    spec: FilesystemSpec,
    *,
    root_partition: str,
    efi_partition: str,
    mount_root: Path,
    home_partition: str | None,
) -> _SimpleMkfsStrategy:
    return _SimpleMkfsStrategy(
        spec=spec,
        root_partition=root_partition,
        efi_partition=efi_partition,
        mount_root=mount_root,
        home_partition=home_partition,
        mkfs_argv=("mkfs.xfs", "-f"),
        description_label="xfs",
    )


def _f2fs_strategy(
    spec: FilesystemSpec,
    *,
    root_partition: str,
    efi_partition: str,
    mount_root: Path,
    home_partition: str | None,
) -> _SimpleMkfsStrategy:
    return _SimpleMkfsStrategy(
        spec=spec,
        root_partition=root_partition,
        efi_partition=efi_partition,
        mount_root=mount_root,
        home_partition=home_partition,
        mkfs_argv=("mkfs.f2fs", "-f"),
        description_label="f2fs",
    )


def build_filesystem_strategy(
    spec: FilesystemSpec,
    *,
    root_partition: str,
    efi_partition: str,
    mount_root: Path,
    home_partition: str | None = None,
) -> Ext4Strategy | BtrfsStrategy | _SimpleMkfsStrategy:
    if spec.kind is FilesystemKind.EXT4:
        return Ext4Strategy(
            spec=spec,
            root_partition=root_partition,
            efi_partition=efi_partition,
            mount_root=mount_root,
            home_partition=home_partition,
        )
    if spec.kind is FilesystemKind.BTRFS:
        return BtrfsStrategy(
            spec=spec,
            root_partition=root_partition,
            efi_partition=efi_partition,
            mount_root=mount_root,
            home_partition=home_partition,
        )
    if spec.kind is FilesystemKind.XFS:
        return _xfs_strategy(
            spec,
            root_partition=root_partition,
            efi_partition=efi_partition,
            mount_root=mount_root,
            home_partition=home_partition,
        )
    if spec.kind is FilesystemKind.F2FS:
        return _f2fs_strategy(
            spec,
            root_partition=root_partition,
            efi_partition=efi_partition,
            mount_root=mount_root,
            home_partition=home_partition,
        )
    raise ValueError(f"unsupported filesystem kind: {spec.kind!r}")
