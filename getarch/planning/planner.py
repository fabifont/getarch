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
from getarch.planning.strategies.bootloader import (
    GrubBiosStrategy,
    build_bootloader_strategy,
)
from getarch.planning.strategies.encryption import build_encryption_strategy
from getarch.planning.strategies.filesystem import build_filesystem_strategy
from getarch.planning.strategies.initramfs import build_initramfs_strategy
from getarch.planning.strategies.mirrors import build_mirror_strategy
from getarch.planning.strategies.mountpoints import (
    MountpointPlan,
    MountpointsStrategy,
)
from getarch.planning.strategies.network import (
    IwdNetworkPlan,
    NetworkConfigStrategy,
    NetworkdProfilePlan,
)
from getarch.planning.strategies.partitioning import SgdiskStrategy
from getarch.planning.strategies.partitioning_bios import SgdiskBiosStrategy
from getarch.planning.strategies.repositories import (
    RepositoriesStrategy,
    RepositoryEntry,
)
from getarch.planning.strategies.snapper import SnapperStrategy
from getarch.planning.strategies.swap import SwapfileStrategy, ZramStrategy

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
        self._extend_pre_disk(steps, cfg, mount_root)
        self._extend_disk_phase(steps, cfg, disk, encrypted=encrypted, mount_root=mount_root)
        self._extend_system_phase(
            steps,
            cfg,
            mount_root,
            disk=disk,
            encrypted=encrypted,
            microcode=microcode,
        )
        self._extend_finalisation(steps, cfg, mount_root)
        try:
            return InstallPlan(version=_PLAN_VERSION, steps=tuple(steps))
        except ValueError as exc:
            raise PlanError(f"plan invalid: {exc}") from exc

    # --- build helpers ---------------------------------------------------

    def _extend_pre_disk(
        self,
        steps: list[PlannedStep],
        cfg: Config,
        mount_root: Path,
    ) -> None:
        # Mirror configuration runs before any destructive disk work so a
        # missing reflector binary or bad reflector_args fails fast (the
        # mirror step only writes to the live ISO mirrorlist anyway).
        mirror_step = self._mirror_step(cfg, mount_root)
        if mirror_step is not None:
            steps.append(mirror_step)
        repos_step = self._repositories_step(cfg)
        if repos_step is not None:
            steps.append(repos_step)

    def _extend_disk_phase(
        self,
        steps: list[PlannedStep],
        cfg: Config,
        disk: Disk,
        *,
        encrypted: bool,
        mount_root: Path,
    ) -> None:
        steps.append(self._partitioning_step(cfg, disk, encrypted=encrypted))
        if encrypted:
            steps.append(self._encryption_step(cfg))
        root_partition = (
            f"/dev/mapper/{cfg.encryption.mapper_name}"
            if encrypted
            else "/dev/disk/by-partlabel/system"
        )
        efi_partition = None if cfg.firmware == "bios" else "/dev/disk/by-partlabel/EFI"
        steps.extend(self._filesystem_steps(cfg, root_partition, efi_partition, mount_root))
        swap_step = self._swap_step(cfg, mount_root)
        if swap_step is not None:
            steps.append(swap_step)
        custom_mounts_step = self._custom_mountpoints_step(cfg, mount_root)
        if custom_mounts_step is not None:
            steps.append(custom_mounts_step)

    def _extend_system_phase(
        self,
        steps: list[PlannedStep],
        cfg: Config,
        mount_root: Path,
        *,
        disk: Disk,
        encrypted: bool,
        microcode: MicrocodeKind,
    ) -> None:
        steps.append(self._packages_step(cfg, mount_root, microcode))
        steps.append(self._fstab_step(mount_root))
        steps.append(self._system_config_step(cfg, mount_root))
        network_step = self._network_config_step(cfg, mount_root)
        if network_step is not None:
            steps.append(network_step)
        steps.append(self._initramfs_step(cfg, mount_root))
        steps.append(
            self._bootloader_step(
                cfg,
                mount_root,
                encrypted=encrypted,
                microcode=microcode,
                disk=disk,
            ),
        )

    def _extend_finalisation(
        self,
        steps: list[PlannedStep],
        cfg: Config,
        mount_root: Path,
    ) -> None:
        services_step = self._services_step(cfg)
        if services_step.commands:
            steps.append(services_step)
        steps.append(self._users_step(cfg))
        if cfg.filesystem.snapper:
            steps.append(self._snapper_step())
        steps.append(self._cleanup_step(cfg, mount_root))
        if cfg.reboot:
            steps.append(self._reboot_step())

    def _partitioning_step(self, cfg: Config, disk: Disk, *, encrypted: bool) -> PlannedStep:
        if cfg.firmware == "bios":
            commands = SgdiskBiosStrategy(
                disk=disk, layout=cfg.partitioning, encrypted=encrypted
            ).commands()
        else:
            commands = SgdiskStrategy(
                disk=disk, layout=cfg.partitioning, encrypted=encrypted
            ).commands()
        return PlannedStep(
            id="partitioning",
            title="Partition disk",
            phase=StepPhase.PARTITIONING,
            commands=commands,
            destructive=True,
            description=(
                f"Create GPT layout {cfg.partitioning.layout!r} "
                f"({cfg.firmware}) on {disk.path.as_posix()}"
            ),
        )

    def _encryption_step(self, cfg: Config) -> PlannedStep:
        spec = EncryptionSpec(
            kind=EncryptionKind.LUKS2,
            password=Secret(cfg.encryption.password or ""),
            mapper_name=cfg.encryption.mapper_name,
            tpm2_unlock=cfg.encryption.tpm2_unlock,
            fido2_unlock=cfg.encryption.fido2_unlock,
            header_path=cfg.encryption.header_path,
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
        efi_partition: str | None,
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
        if cfg.network.backend == "iwd" and "iwd" not in pkgs:
            pkgs.append("iwd")
        if cfg.swap.kind == "zram" and "zram-generator" not in pkgs:
            pkgs.append("zram-generator")
        if cfg.filesystem.snapper and "snapper" not in pkgs:
            pkgs.append("snapper")
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
        encrypted = cfg.encryption.kind == "luks2"
        encryption_spec = EncryptionSpec(
            kind=EncryptionKind.LUKS2 if encrypted else EncryptionKind.NONE,
            password=(
                Secret(cfg.encryption.password)
                if encrypted and cfg.encryption.password
                else None
            ),
            mapper_name=cfg.encryption.mapper_name,
            tpm2_unlock=cfg.encryption.tpm2_unlock,
            fido2_unlock=cfg.encryption.fido2_unlock,
            header_path=cfg.encryption.header_path,
        )
        strategy = build_initramfs_strategy(
            generator=cfg.initramfs.generator,
            hooks=tuple(cfg.initramfs.hooks),
            kernel=KernelSpec(kind=KernelKind(cfg.kernel.kind)),
            encryption=encryption_spec,
            mount_root=mount_root,
        )
        return PlannedStep(
            id="initramfs",
            title="Generate initramfs",
            phase=StepPhase.INITRAMFS,
            commands=strategy.commands(),
            destructive=False,
            description=f"generate initramfs via {cfg.initramfs.generator}",
        )

    def _bootloader_step(
        self,
        cfg: Config,
        mount_root: Path,
        *,
        encrypted: bool,
        microcode: MicrocodeKind,
        disk: Disk,
    ) -> PlannedStep:
        rootflags = "rootflags=subvol=@" if cfg.filesystem.kind == "btrfs" else None
        bl_spec = BootloaderSpec(
            kind=BootloaderKind(cfg.bootloader.kind),
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
            tpm2_unlock=cfg.encryption.tpm2_unlock,
            fido2_unlock=cfg.encryption.fido2_unlock,
            header_path=cfg.encryption.header_path,
        )
        if cfg.firmware == "bios":
            strategy_cmds = GrubBiosStrategy(
                spec=bl_spec,
                kernel=KernelSpec(kind=KernelKind(cfg.kernel.kind)),
                microcode=microcode,
                encryption=encryption_spec,
                rootflags=rootflags,
                crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
                mount_root=mount_root,
                install_disk=disk.path.as_posix(),
            ).commands()
        else:
            strategy_cmds = build_bootloader_strategy(
                bl_spec,
                kernel=KernelSpec(kind=KernelKind(cfg.kernel.kind)),
                microcode=microcode,
                encryption=encryption_spec,
                rootflags=rootflags,
                crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
                mount_root=mount_root,
            ).commands()
        return PlannedStep(
            id="bootloader",
            title="Install bootloader",
            phase=StepPhase.BOOTLOADER,
            commands=strategy_cmds,
            destructive=False,
            description=f"install {cfg.bootloader.kind} bootloader ({cfg.firmware})",
        )

    def _services_step(self, cfg: Config) -> PlannedStep:
        enable = list(cfg.services.enable)
        timers = list(cfg.services.timers)
        # Backend-driven services so first boot actually has networking.
        if cfg.network.backend == "systemd-networkd":
            for svc in ("systemd-networkd", "systemd-resolved"):
                if svc not in enable:
                    enable.append(svc)
        elif cfg.network.backend == "iwd" and "iwd" not in enable:
            enable.append("iwd")
        if cfg.filesystem.snapper:
            for unit in ("snapper-timeline.timer", "snapper-cleanup.timer"):
                if unit not in timers and unit not in enable:
                    timers.append(unit)
        svc_cmds = tuple(
            Command(
                argv=("systemctl", "enable", svc),
                chroot=True,
                description=f"enable {svc}",
            )
            for svc in (*enable, *timers)
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

    def _snapper_step(self) -> PlannedStep:
        return PlannedStep(
            id="snapper",
            title="Initialise snapper",
            phase=StepPhase.SYSTEM_CONFIG,
            commands=SnapperStrategy().commands(),
            destructive=False,
            description="snapper create-config / for periodic snapshots",
        )

    def _cleanup_step(self, cfg: Config, mount_root: Path) -> PlannedStep:
        cmds: list[Command] = []
        if cfg.swap.kind == "swapfile":
            cmds.append(
                Command(
                    argv=("swapoff", str(mount_root / "swap/swapfile")),
                    check=False,
                    description="deactivate swapfile so target filesystem is not busy",
                ),
            )
        cmds.append(
            Command(
                argv=(
                    "sh",
                    "-c",
                    f"umount -R {mount_root} || umount -lR {mount_root}",
                ),
                description=(
                    f"unmount target, falling back to lazy unmount on busy ({mount_root})"
                ),
            ),
        )
        return PlannedStep(
            id="cleanup",
            title="Unmount target",
            phase=StepPhase.CLEANUP,
            commands=tuple(cmds),
            destructive=False,
            description=f"umount -R {mount_root} with lazy fallback",
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
            # snapper manages /.snapshots itself: dropping @snapshots from
            # the planner-built subvolume list avoids the conflict where
            # `snapper create-config /` would try to take over an already
            # mounted @snapshots subvolume.
            subs = tuple(
                BtrfsSubvolume(name=s.name, mountpoint=Path(s.mountpoint))
                for s in cfg.filesystem.subvolumes
                if not (drop_home_subvolume and s.mountpoint == "/home")
                and not (cfg.filesystem.snapper and s.mountpoint == "/.snapshots")
            )
            return FilesystemSpec(
                kind=FilesystemKind.BTRFS,
                label=cfg.filesystem.label,
                mount_options=opts,
                subvolumes=subs,
            )
        return FilesystemSpec(
            kind=FilesystemKind(cfg.filesystem.kind),
            label=cfg.filesystem.label,
        )

    def _network_config_step(
        self,
        cfg: Config,
        mount_root: Path,
    ) -> PlannedStep | None:
        if cfg.network.backend == "networkmanager":
            return None
        profiles = tuple(
            NetworkdProfilePlan(
                name=p.name,
                match=dict(p.match),
                network=dict(p.network),
            )
            for p in cfg.network.systemd_networkd
        )
        iwd = tuple(
            IwdNetworkPlan(ssid=n.ssid, psk=n.psk)
            for n in cfg.network.iwd_networks
        )
        if not profiles and not iwd:
            return None
        cmds = NetworkConfigStrategy(
            backend=cfg.network.backend,
            networkd_profiles=profiles,
            iwd_networks=iwd,
            mount_root=mount_root,
        ).commands()
        return PlannedStep(
            id="network-config",
            title="Render network configuration",
            phase=StepPhase.SYSTEM_CONFIG,
            commands=cmds,
            destructive=False,
            description=f"render {cfg.network.backend} configuration files",
        )

    def _custom_mountpoints_step(
        self,
        cfg: Config,
        mount_root: Path,
    ) -> PlannedStep | None:
        if not cfg.mountpoints:
            return None
        plans = tuple(
            MountpointPlan(
                partition_label=m.partition_label,
                mountpoint=m.mountpoint,
                mount_options=tuple(m.mount_options),
            )
            for m in cfg.mountpoints
        )
        cmds = MountpointsStrategy(plans=plans, mount_root=mount_root).commands()
        return PlannedStep(
            id="custom-mountpoints",
            title="Mount user-declared partitions",
            phase=StepPhase.MOUNTING,
            commands=cmds,
            destructive=False,
            description=f"mount {len(plans)} extra existing partitions",
        )

    def _swap_step(self, cfg: Config, mount_root: Path) -> PlannedStep | None:
        if cfg.swap.kind == "swapfile":
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
        if cfg.swap.kind == "zram":
            return PlannedStep(
                id="swap",
                title="Configure zram swap",
                phase=StepPhase.SWAP,
                commands=ZramStrategy(
                    mount_root=mount_root,
                    size_mib=cfg.swap.zram_size_mib,
                ).commands(),
                destructive=False,
                description="write zram-generator.conf for /dev/zram0",
            )
        return None

    def _repositories_step(self, cfg: Config) -> PlannedStep | None:
        repos = cfg.repositories
        extras = tuple(
            RepositoryEntry(name=r.name, include=r.include) for r in repos.extra
        )
        if not repos.multilib and not extras:
            return None
        cmds = RepositoriesStrategy(
            multilib=repos.multilib,
            extras=extras,
        ).commands()
        if not cmds:
            return None
        return PlannedStep(
            id="repositories",
            title="Configure pacman repositories",
            phase=StepPhase.MIRRORS,
            commands=cmds,
            destructive=False,
            description=(
                f"multilib={repos.multilib}, extras={[e.name for e in extras]}"
            ),
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
