"""Planner - turns a Config + Disk into an InstallPlan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.config.schema.v1 import Config
from getarch.constants import DEFAULT_BTRFS_MOUNT_OPTIONS
from getarch.domain.bootloader import BootloaderKind, BootloaderSpec
from getarch.domain.disk import Disk
from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.filesystem import (
    BtrfsSubvolume,
    FilesystemKind,
    FilesystemSpec,
)
from getarch.domain.kernel import KernelKind, KernelSpec, MicrocodeKind
from getarch.domain.plan import InstallPlan, PlannedStep, StepPhase
from getarch.domain.secret import Secret
from getarch.errors import PlanError
from getarch.execution.command import Command
from getarch.planning.strategies.bootloader import SystemdBootStrategy
from getarch.planning.strategies.encryption import build_encryption_strategy
from getarch.planning.strategies.filesystem import build_filesystem_strategy
from getarch.planning.strategies.initramfs import MkinitcpioStrategy
from getarch.planning.strategies.mirrors import build_mirror_strategy
from getarch.planning.strategies.partitioning import SgdiskStrategy
from getarch.planning.strategies.swap import SwapfileStrategy

_PLAN_VERSION = "1"


@dataclass(slots=True)
class Planner:
    def build(
        self,
        *,
        cfg: Config,
        disk: Disk,
        mount_root: Path,
        cpu_vendor: str | None = None,
    ) -> InstallPlan:
        encrypted = cfg.encryption.kind == "luks2"
        microcode = self._resolve_microcode(cfg, cpu_vendor)
        steps: list[PlannedStep] = []

        steps.append(self._partitioning_step(cfg, disk, encrypted=encrypted))
        if encrypted:
            steps.append(self._encryption_step(cfg))

        root_partition = (
            f"/dev/mapper/{cfg.encryption.mapper_name}"
            if encrypted
            else "/dev/disk/by-partlabel/system"
        )
        efi_partition = "/dev/disk/by-partlabel/EFI"
        fs_steps = self._filesystem_steps(cfg, root_partition, efi_partition, mount_root)
        steps.extend(fs_steps)

        swap_step = self._swap_step(cfg, mount_root)
        if swap_step is not None:
            steps.append(swap_step)

        mirror_step = self._mirror_step(cfg, mount_root)
        if mirror_step is not None:
            steps.append(mirror_step)
        steps.append(self._packages_step(cfg, mount_root, microcode))
        steps.append(self._fstab_step(mount_root))
        steps.append(self._system_config_step(cfg, mount_root))
        steps.append(self._initramfs_step(cfg, mount_root))
        steps.append(
            self._bootloader_step(cfg, mount_root, encrypted=encrypted, microcode=microcode),
        )
        if cfg.services.enable or cfg.services.timers:
            steps.append(self._services_step(cfg))
        steps.append(self._users_step(cfg))
        steps.append(self._cleanup_step(mount_root))
        if cfg.reboot:
            steps.append(self._reboot_step())

        try:
            return InstallPlan(version=_PLAN_VERSION, steps=tuple(steps))
        except ValueError as exc:
            raise PlanError(f"plan invalid: {exc}") from exc

    def _partitioning_step(self, cfg: Config, disk: Disk, *, encrypted: bool) -> PlannedStep:
        return PlannedStep(
            id="partitioning",
            title="Partition disk",
            phase=StepPhase.PARTITIONING,
            commands=SgdiskStrategy(
                disk=disk, layout=cfg.partitioning, encrypted=encrypted
            ).commands(),
            destructive=True,
            description=(
                f"Create GPT layout {cfg.partitioning.layout!r} on {disk.path.as_posix()}"
            ),
        )

    def _encryption_step(self, cfg: Config) -> PlannedStep:
        spec = EncryptionSpec(
            kind=EncryptionKind.LUKS2,
            password=Secret(cfg.encryption.password or ""),
            mapper_name=cfg.encryption.mapper_name,
        )
        return PlannedStep(
            id="encryption",
            title="Set up LUKS2 root",
            phase=StepPhase.ENCRYPTION,
            commands=build_encryption_strategy(spec).commands(),
            destructive=True,
            description="luksFormat then open root partition",
        )

    def _filesystem_steps(
        self,
        cfg: Config,
        root_partition: str,
        efi_partition: str,
        mount_root: Path,
    ) -> tuple[PlannedStep, PlannedStep]:
        has_home = "home" in cfg.partitioning.layout
        fs_spec = self._fs_spec(cfg, drop_home_subvolume=has_home)
        home_partition = "/dev/disk/by-partlabel/home" if has_home else None
        fs_cmds = build_filesystem_strategy(
            spec=fs_spec,
            root_partition=root_partition,
            efi_partition=efi_partition,
            mount_root=mount_root,
            home_partition=home_partition,
        ).commands()
        mkfs_cmds = tuple(c for c in fs_cmds if c.argv[0].startswith("mkfs"))
        mount_cmds = tuple(c for c in fs_cmds if c not in mkfs_cmds)
        fs_step = PlannedStep(
            id="filesystems",
            title="Create filesystems",
            phase=StepPhase.FILESYSTEMS,
            commands=mkfs_cmds,
            destructive=True,
            description=f"create {cfg.filesystem.kind} root + FAT32 EFI",
        )
        mount_step = PlannedStep(
            id="mounting",
            title="Mount filesystems",
            phase=StepPhase.MOUNTING,
            commands=mount_cmds,
            destructive=False,
            description=f"mount root and ESP under {mount_root}",
        )
        return fs_step, mount_step

    def _packages_step(
        self,
        cfg: Config,
        mount_root: Path,
        microcode: MicrocodeKind,
    ) -> PlannedStep:
        pkgs = list(cfg.packages)
        ucode = microcode.package_name
        if ucode and ucode not in pkgs:
            pkgs.append(ucode)
        if cfg.network.backend == "networkmanager" and "networkmanager" not in pkgs:
            pkgs.append("networkmanager")
        return PlannedStep(
            id="packages",
            title="Pacstrap base packages",
            phase=StepPhase.PACKAGES,
            commands=(
                Command(
                    argv=("pacstrap", "-K", str(mount_root), *pkgs),
                    description=f"install {len(pkgs)} packages into {mount_root}",
                ),
            ),
            destructive=False,
            description="install base packages into the new system",
        )

    def _fstab_step(self, mount_root: Path) -> PlannedStep:
        return PlannedStep(
            id="fstab",
            title="Generate fstab",
            phase=StepPhase.FSTAB,
            commands=(
                Command(
                    argv=(
                        "sh",
                        "-c",
                        f"genfstab -L -p {mount_root} >> {mount_root}/etc/fstab",
                    ),
                    description="genfstab -L -p (label-based)",
                ),
            ),
            destructive=False,
            description=f"write {mount_root}/etc/fstab",
        )

    def _system_config_step(self, cfg: Config, mount_root: Path) -> PlannedStep:
        return PlannedStep(
            id="system_config",
            title="System configuration",
            phase=StepPhase.SYSTEM_CONFIG,
            commands=self._system_config_commands(cfg, mount_root),
            destructive=False,
            description="locale, timezone, hostname, hosts, vconsole",
        )

    def _initramfs_step(self, cfg: Config, mount_root: Path) -> PlannedStep:
        return PlannedStep(
            id="initramfs",
            title="Generate initramfs",
            phase=StepPhase.INITRAMFS,
            commands=MkinitcpioStrategy(
                hooks=tuple(cfg.initramfs.hooks),
                kernel=KernelSpec(kind=KernelKind(cfg.kernel.kind)),
                mount_root=mount_root,
            ).commands(),
            destructive=False,
            description="write hooks snippet and run mkinitcpio",
        )

    def _bootloader_step(
        self,
        cfg: Config,
        mount_root: Path,
        *,
        encrypted: bool,
        microcode: MicrocodeKind,
    ) -> PlannedStep:
        rootflags = "rootflags=subvol=@" if cfg.filesystem.kind == "btrfs" else None
        bl_spec = BootloaderSpec(
            kind=BootloaderKind.SYSTEMD_BOOT,
            entry_id=cfg.bootloader.entry_id,
            timeout_seconds=cfg.bootloader.timeout_seconds,
            extra_kernel_params=tuple(cfg.bootloader.extra_kernel_params),
        )
        encryption_spec = EncryptionSpec(
            kind=EncryptionKind.LUKS2 if encrypted else EncryptionKind.NONE,
            password=(
                Secret(cfg.encryption.password) if encrypted and cfg.encryption.password else None
            ),
            mapper_name=cfg.encryption.mapper_name,
        )
        return PlannedStep(
            id="bootloader",
            title="Install bootloader",
            phase=StepPhase.BOOTLOADER,
            commands=SystemdBootStrategy(
                spec=bl_spec,
                kernel=KernelSpec(kind=KernelKind(cfg.kernel.kind)),
                microcode=microcode,
                encryption=encryption_spec,
                rootflags=rootflags,
                crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
                mount_root=mount_root,
            ).commands(),
            destructive=False,
            description="install systemd-boot and write loader entry",
        )

    def _services_step(self, cfg: Config) -> PlannedStep:
        svc_cmds = tuple(
            Command(
                argv=("systemctl", "enable", svc),
                chroot=True,
                description=f"enable {svc}",
            )
            for svc in (*cfg.services.enable, *cfg.services.timers)
        )
        return PlannedStep(
            id="services",
            title="Enable services and timers",
            phase=StepPhase.SERVICES,
            commands=svc_cmds,
            destructive=False,
            description="systemctl enable for declared units",
        )

    def _users_step(self, cfg: Config) -> PlannedStep:
        return PlannedStep(
            id="users",
            title="Configure users",
            phase=StepPhase.USERS,
            commands=self._user_commands(cfg),
            destructive=False,
            description="set root password and create regular users",
        )

    def _cleanup_step(self, mount_root: Path) -> PlannedStep:
        return PlannedStep(
            id="cleanup",
            title="Unmount target",
            phase=StepPhase.CLEANUP,
            commands=(
                Command(
                    argv=("umount", "-R", str(mount_root)),
                    description="recursively unmount target",
                ),
            ),
            destructive=False,
            description=f"umount -R {mount_root}",
        )

    def _reboot_step(self) -> PlannedStep:
        return PlannedStep(
            id="reboot",
            title="Reboot",
            phase=StepPhase.REBOOT,
            commands=(Command(argv=("reboot",), description="systemctl reboot"),),
            destructive=False,
            description="reboot into the new system",
        )

    def _fs_spec(self, cfg: Config, *, drop_home_subvolume: bool = False) -> FilesystemSpec:
        if cfg.filesystem.kind == "btrfs":
            opts = tuple(cfg.filesystem.mount_options) or DEFAULT_BTRFS_MOUNT_OPTIONS
            subs = tuple(
                BtrfsSubvolume(name=s.name, mountpoint=Path(s.mountpoint))
                for s in cfg.filesystem.subvolumes
                if not (drop_home_subvolume and s.mountpoint == "/home")
            )
            return FilesystemSpec(
                kind=FilesystemKind.BTRFS,
                label=cfg.filesystem.label,
                mount_options=opts,
                subvolumes=subs,
            )
        return FilesystemSpec(kind=FilesystemKind.EXT4, label=cfg.filesystem.label)

    def _swap_step(self, cfg: Config, mount_root: Path) -> PlannedStep | None:
        if cfg.swap.kind != "swapfile":
            return None
        size = cfg.swap.size_mib
        if size is None:
            raise PlanError("swap.size_mib required for kind='swapfile'")
        return PlannedStep(
            id="swap",
            title="Create swapfile",
            phase=StepPhase.SWAP,
            commands=SwapfileStrategy(
                size_mib=size,
                mount_root=mount_root,
                btrfs=cfg.filesystem.kind == "btrfs",
            ).commands(),
            destructive=False,
            description=f"create {size} MiB swapfile",
        )

    def _mirror_step(self, cfg: Config, mount_root: Path) -> PlannedStep | None:
        strategy = build_mirror_strategy(cfg.mirrors, mount_root)
        if strategy is None:
            return None
        return PlannedStep(
            id="mirrors",
            title="Configure pacman mirrors",
            phase=StepPhase.MIRRORS,
            commands=strategy.commands(),
            destructive=False,
            description=f"mirrors strategy: {cfg.mirrors.strategy}",
        )

    def _resolve_microcode(self, cfg: Config, cpu_vendor: str | None) -> MicrocodeKind:
        if cfg.microcode.kind == "intel":
            return MicrocodeKind.INTEL
        if cfg.microcode.kind == "amd":
            return MicrocodeKind.AMD
        if cfg.microcode.kind == "none":
            return MicrocodeKind.NONE
        return MicrocodeKind.from_cpu_vendor(cpu_vendor)

    def _system_config_commands(self, cfg: Config, mount_root: Path) -> tuple[Command, ...]:
        return (
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    "/dev/stdin",
                    str(mount_root / "etc/locale.conf"),
                ),
                input=f"LANG={cfg.locale.lang}\n",
                description="write /etc/locale.conf",
            ),
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    "/dev/stdin",
                    str(mount_root / "etc/locale.gen"),
                ),
                input=f"{cfg.locale.locale}\n",
                description="write /etc/locale.gen",
            ),
            Command(
                argv=("locale-gen",),
                chroot=True,
                description="run locale-gen",
            ),
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    "/dev/stdin",
                    str(mount_root / "etc/vconsole.conf"),
                ),
                input=f"KEYMAP={cfg.locale.keymap}\n",
                description="write /etc/vconsole.conf",
            ),
            Command(
                argv=(
                    "ln",
                    "-sf",
                    f"/usr/share/zoneinfo/{cfg.locale.timezone}",
                    "/etc/localtime",
                ),
                chroot=True,
                description=f"set timezone to {cfg.locale.timezone}",
            ),
            Command(
                argv=("hwclock", "--systohc"),
                chroot=True,
                description="sync hardware clock",
            ),
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    "/dev/stdin",
                    str(mount_root / "etc/hostname"),
                ),
                input=f"{cfg.network.hostname}\n",
                description="write /etc/hostname",
            ),
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    "/dev/stdin",
                    str(mount_root / "etc/hosts"),
                ),
                input=(
                    "127.0.0.1 localhost\n"
                    "::1       localhost\n"
                    f"127.0.1.1 {cfg.network.hostname}.localdomain "
                    f"{cfg.network.hostname}\n"
                ),
                description="write /etc/hosts",
            ),
        )

    def _user_commands(self, cfg: Config) -> tuple[Command, ...]:
        cmds: list[Command] = []
        if cfg.users.root.kind == "plain" and cfg.users.root.password:
            cmds.append(
                Command(
                    argv=("chpasswd",),
                    chroot=True,
                    input=f"root:{cfg.users.root.password}\n",
                    sensitive=True,
                    description="set root password",
                ),
            )
        elif cfg.users.root.kind == "hashed" and cfg.users.root.hashed:
            cmds.append(
                Command(
                    argv=("chpasswd", "-e"),
                    chroot=True,
                    input=f"root:{cfg.users.root.hashed}\n",
                    sensitive=True,
                    description="set root password (pre-hashed)",
                ),
            )
        for u in cfg.users.regular:
            args = ["useradd", "-m" if u.create_home else "-M", "-s", u.shell]
            if u.groups:
                args.extend(["-G", ",".join(u.groups)])
            args.append(u.username)
            cmds.append(
                Command(
                    argv=tuple(args),
                    chroot=True,
                    description=f"create user {u.username}",
                ),
            )
            if u.password:
                cmds.append(
                    Command(
                        argv=("chpasswd",),
                        chroot=True,
                        input=f"{u.username}:{u.password}\n",
                        sensitive=True,
                        description=f"set password for {u.username}",
                    ),
                )
            elif u.hashed_password:
                cmds.append(
                    Command(
                        argv=("chpasswd", "-e"),
                        chroot=True,
                        input=f"{u.username}:{u.hashed_password}\n",
                        sensitive=True,
                        description=f"set hashed password for {u.username}",
                    ),
                )
            if u.sudo:
                cmds.append(
                    Command(
                        argv=(
                            "install",
                            "-Dm440",
                            "/dev/stdin",
                            f"/etc/sudoers.d/10-{u.username}",
                        ),
                        chroot=True,
                        input=f"{u.username} ALL=(ALL:ALL) ALL\n",
                        description=f"grant sudo to {u.username}",
                    ),
                )
        return tuple(cmds)
