"""Bootloader strategies (systemd-boot, GRUB, UKI).

Per Arch Wiki / `bootctl(1)`: ``bootctl install`` from inside ``arch-chroot``
runs inside a pid namespace and refuses to write UEFI variables. We therefore
run ``bootctl`` against ``--esp-path=<mount_root>/boot`` from the live ISO
directly (``chroot=False``).

For non-encrypted root, the kernel cmdline uses ``root=LABEL=system`` because
the filesystem strategy labels the root filesystem. Nothing dynamic at boot.

For LUKS2 root, the LUKS UUID can only be discovered *after* ``cryptsetup
luksFormat``. The strategy emits one ``bash -c`` script that runs ``blkid`` at
execution time to capture the UUID, then writes the loader entry via a
heredoc. ``subprocess.run`` is still called with ``shell=False``; the script
content is built only from validated config values.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.domain.bootloader import BootloaderKind, BootloaderSpec
from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.kernel import KernelSpec, MicrocodeKind
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class SystemdBootStrategy:
    spec: BootloaderSpec
    kernel: KernelSpec
    microcode: MicrocodeKind
    encryption: EncryptionSpec
    rootflags: str | None
    crypt_partition_path: str
    mount_root: Path
    root_device: str = ""
    root_label: str = "system"

    def commands(self) -> tuple[Command, ...]:
        loader_conf = self.mount_root / "boot/loader/loader.conf"
        entry = self.mount_root / "boot/loader/entries" / f"{self.spec.entry_id}.conf"
        loader_text = (
            f"default {self.spec.entry_id}.conf\n"
            f"timeout {self.spec.timeout_seconds}\n"
            f"console-mode auto\n"
            f"editor no\n"
        )
        cmds: list[Command] = [
            Command(
                argv=("bootctl", f"--esp-path={self.mount_root}/boot", "install"),
                chroot=False,
                description="install systemd-boot to ESP (run outside chroot for EFI vars)",
            ),
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(loader_conf)),
                input=loader_text,
                description=f"write {loader_conf}",
            ),
        ]
        entry_text = self._entry_text()
        if self.encryption.kind is EncryptionKind.LUKS2:
            script = (
                "set -euo pipefail\n"
                f'LUKS_UUID="$(blkid -s UUID -o value {self.crypt_partition_path})"\n'
                f"install -Dm644 /dev/stdin {entry} <<EOF\n"
                f"{entry_text}\n"
                "EOF\n"
            )
            cmds.append(
                Command(
                    argv=("bash", "-c", script),
                    description=f"write {entry} with discovered LUKS UUID",
                ),
            )
        else:
            cmds.append(
                Command(
                    argv=("install", "-Dm644", "/dev/stdin", str(entry)),
                    input=entry_text + "\n",
                    description=f"write {entry}",
                ),
            )
        return tuple(cmds)

    def _entry_text(self) -> str:
        params: list[str] = []
        if self.encryption.kind is EncryptionKind.LUKS2:
            params.append(f"rd.luks.name=${{LUKS_UUID}}={self.encryption.mapper_name}")
            # Combine all rd.luks.options into a single comma-separated
            # value: sd-encrypt parses one occurrence per kernel cmdline.
            luks_options: list[str] = ["discard"]
            if self.encryption.header_path:
                luks_options.append(f"header={self.encryption.header_path}")
            if self.encryption.tpm2_unlock:
                luks_options.append("tpm2-device=auto")
            if self.encryption.fido2_unlock:
                luks_options.append("fido2-device=auto")
            params.append(f"rd.luks.options={','.join(luks_options)}")
            root = self.root_device or f"/dev/mapper/{self.encryption.mapper_name}"
            params.append(f"root={root}")
        else:
            params.append(f"root=LABEL={self.root_label}")
        if self.rootflags:
            params.append(self.rootflags)
        params.append("rw")
        params.extend(self.spec.extra_kernel_params)
        options = " ".join(params)
        text = "title Arch Linux\n"
        text += f"linux /{self.kernel.image_filename}\n"
        if self.microcode.package_name:
            text += f"initrd /{self.microcode.package_name}.img\n"
        text += f"initrd /{self.kernel.initramfs_filename}\n"
        text += f"options {options}"
        return text


@dataclass(frozen=True, slots=True)
class GrubStrategy:
    """Install GRUB onto the ESP and write its config.

    Cmdline assembly mirrors :class:`SystemdBootStrategy` but is rendered
    into ``/etc/default/grub`` so ``grub-mkconfig`` picks it up. ``grub-install``
    runs in chroot because GRUB writes UEFI variables only when invoked
    against a real EFI mount inside the target — Arch's recommendation.
    """

    spec: BootloaderSpec
    kernel: KernelSpec
    microcode: MicrocodeKind
    encryption: EncryptionSpec
    rootflags: str | None
    crypt_partition_path: str
    mount_root: Path
    root_device: str = ""
    root_label: str = "system"

    def commands(self) -> tuple[Command, ...]:
        defaults_path = self.mount_root / "etc/default/grub"
        cmdline = self._cmdline()
        defaults_text = (
            f"GRUB_DEFAULT=0\n"
            f"GRUB_TIMEOUT={self.spec.timeout_seconds}\n"
            f'GRUB_DISTRIBUTOR="Arch"\n'
            f'GRUB_CMDLINE_LINUX_DEFAULT="{cmdline}"\n'
            f'GRUB_PRELOAD_MODULES="part_gpt part_msdos"\n'
        )
        cmds: list[Command] = [
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(defaults_path)),
                input=defaults_text,
                description=f"write {defaults_path}",
            ),
            Command(
                argv=(
                    "grub-install",
                    "--target=x86_64-efi",
                    "--efi-directory=/boot",
                    f"--bootloader-id={self.spec.entry_id}",
                ),
                chroot=True,
                description="install GRUB EFI binary into ESP",
            ),
        ]
        if self.encryption.kind is EncryptionKind.LUKS2:
            # GRUB needs to know how to crypto-unlock at boot: enable cryptodisk.
            cmds.append(
                Command(
                    argv=(
                        "sh",
                        "-c",
                        (f"printf 'GRUB_ENABLE_CRYPTODISK=y\\n' >> {defaults_path}"),
                    ),
                    description="enable cryptodisk in /etc/default/grub",
                ),
            )
        cmds.append(
            Command(
                argv=("grub-mkconfig", "-o", "/boot/grub/grub.cfg"),
                chroot=True,
                description="render /boot/grub/grub.cfg",
            ),
        )
        return tuple(cmds)

    def _cmdline(self) -> str:
        params: list[str] = []
        if self.encryption.kind is EncryptionKind.LUKS2:
            # mkinitcpio's busybox `encrypt` hook accepts an inline
            # header= via the cryptdevice= argument; the systemd
            # `sd-encrypt` hook reads `rd.luks.options=header=`. Emit
            # both so either initramfs flavour boots.
            cryptdevice = f"cryptdevice={self.crypt_partition_path}:{self.encryption.mapper_name}"
            if self.encryption.header_path:
                cryptdevice = f"{cryptdevice}:header={self.encryption.header_path}"
            params.append(cryptdevice)
            root = self.root_device or f"/dev/mapper/{self.encryption.mapper_name}"
            params.append(f"root={root}")
            luks_options: list[str] = []
            if self.encryption.header_path:
                luks_options.append(f"header={self.encryption.header_path}")
            if self.encryption.tpm2_unlock:
                luks_options.append("tpm2-device=auto")
            if self.encryption.fido2_unlock:
                luks_options.append("fido2-device=auto")
            if luks_options:
                params.append(f"rd.luks.options={','.join(luks_options)}")
        else:
            params.append(f"root=LABEL={self.root_label}")
        if self.rootflags:
            params.append(self.rootflags)
        params.append("rw")
        params.extend(self.spec.extra_kernel_params)
        return " ".join(params)


@dataclass(frozen=True, slots=True)
class UkiStrategy:
    """Unified Kernel Image strategy.

    Writes a mkinitcpio preset that emits a UKI to
    ``/boot/EFI/Linux/<entry_id>-<kernel>.efi`` (the ESP that the
    filesystem strategy already mounted at ``/boot``). Also installs
    systemd-boot so users get a graphical boot picker when multiple UKIs
    exist.

    For LUKS roots, the kernel cmdline must reference the *encrypted
    partition's* UUID. That UUID is only known after ``cryptsetup
    luksFormat`` runs, so we resolve it at execution time via a small
    ``bash -c`` script that runs ``blkid`` and writes
    ``/etc/kernel/cmdline`` before invoking ``mkinitcpio``.
    """

    spec: BootloaderSpec
    kernel: KernelSpec
    microcode: MicrocodeKind
    encryption: EncryptionSpec
    rootflags: str | None
    crypt_partition_path: str
    mount_root: Path
    root_device: str = ""
    root_label: str = "system"

    def commands(self) -> tuple[Command, ...]:
        preset_path = self.mount_root / "etc/mkinitcpio.d" / f"{self.kernel.kind.value}.preset"
        cmdline_path = self.mount_root / "etc/kernel/cmdline"
        uki_path = f"/boot/EFI/Linux/{self.spec.entry_id}-{self.kernel.kind.value}.efi"
        preset_text = (
            f'ALL_kver="/boot/{self.kernel.image_filename}"\n'
            f"ALL_microcode=()\n"
            f"PRESETS=('default')\n"
            f'default_uki="{uki_path}"\n'
            f'default_options="--splash /usr/share/systemd/bootctl/splash-arch.bmp"\n'
        )
        cmds: list[Command] = []
        if self.encryption.kind is EncryptionKind.LUKS2:
            # Resolve the LUKS UUID at execution time, then write the
            # cmdline atomically.
            cmdline_template = self._cmdline_with_uuid_placeholder()
            script = (
                "set -euo pipefail\n"
                f'LUKS_UUID="$(blkid -s UUID -o value {self.crypt_partition_path})"\n'
                f"install -Dm644 /dev/stdin {cmdline_path} <<EOF\n"
                f"{cmdline_template}\n"
                "EOF\n"
            )
            cmds.append(
                Command(
                    argv=("bash", "-c", script),
                    description=f"write {cmdline_path} with discovered LUKS UUID",
                ),
            )
        else:
            cmds.append(
                Command(
                    argv=("install", "-Dm644", "/dev/stdin", str(cmdline_path)),
                    input=self._cmdline_static() + "\n",
                    description=f"write {cmdline_path}",
                ),
            )
        cmds.extend(
            (
                Command(
                    argv=("install", "-Dm644", "/dev/stdin", str(preset_path)),
                    input=preset_text,
                    description=f"write {preset_path}",
                ),
                Command(
                    argv=("mkdir", "-p", str(self.mount_root / "boot/EFI/Linux")),
                    description="create UKI output directory on ESP",
                ),
                Command(
                    argv=("mkinitcpio", "-p", self.kernel.kind.value),
                    chroot=True,
                    description="regenerate UKI via mkinitcpio preset",
                ),
                Command(
                    argv=("bootctl", f"--esp-path={self.mount_root}/boot", "install"),
                    chroot=False,
                    description="install systemd-boot loader (chains UKIs)",
                ),
            ),
        )
        return tuple(cmds)

    def _cmdline_static(self) -> str:
        params: list[str] = [f"root=LABEL={self.root_label}"]
        if self.rootflags:
            params.append(self.rootflags)
        params.append("rw")
        params.extend(self.spec.extra_kernel_params)
        return " ".join(params)

    def _cmdline_with_uuid_placeholder(self) -> str:
        # The script substitutes ${LUKS_UUID} via the bash heredoc.
        root = self.root_device or f"/dev/mapper/{self.encryption.mapper_name}"
        params: list[str] = [
            f"rd.luks.name=${{LUKS_UUID}}={self.encryption.mapper_name}",
            f"root={root}",
        ]
        luks_options: list[str] = []
        if self.encryption.header_path:
            luks_options.append(f"header={self.encryption.header_path}")
        if self.encryption.tpm2_unlock:
            luks_options.append("tpm2-device=auto")
        if self.encryption.fido2_unlock:
            luks_options.append("fido2-device=auto")
        if luks_options:
            params.append(f"rd.luks.options={','.join(luks_options)}")
        if self.rootflags:
            params.append(self.rootflags)
        params.append("rw")
        params.extend(self.spec.extra_kernel_params)
        return " ".join(params)


@dataclass(frozen=True, slots=True)
class GrubBiosStrategy:
    """GRUB on a non-UEFI (BIOS / legacy) target.

    Installs GRUB stage 1/1.5 to the MBR + BIOS-boot partition with
    ``grub-install --target=i386-pc <disk>``. Cmdline assembly mirrors
    :class:`GrubStrategy`.
    """

    spec: BootloaderSpec
    kernel: KernelSpec
    microcode: MicrocodeKind
    encryption: EncryptionSpec
    rootflags: str | None
    crypt_partition_path: str
    mount_root: Path
    install_disk: str
    root_device: str = ""
    root_label: str = "system"

    def commands(self) -> tuple[Command, ...]:
        defaults_path = self.mount_root / "etc/default/grub"
        cmdline = self._cmdline()
        defaults_text = (
            f"GRUB_DEFAULT=0\n"
            f"GRUB_TIMEOUT={self.spec.timeout_seconds}\n"
            f'GRUB_DISTRIBUTOR="Arch"\n'
            f'GRUB_CMDLINE_LINUX_DEFAULT="{cmdline}"\n'
            f'GRUB_PRELOAD_MODULES="part_gpt part_msdos"\n'
        )
        cmds: list[Command] = [
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(defaults_path)),
                input=defaults_text,
                description=f"write {defaults_path}",
            ),
            Command(
                argv=(
                    "grub-install",
                    "--target=i386-pc",
                    self.install_disk,
                ),
                chroot=True,
                description=f"install GRUB BIOS stage to {self.install_disk}",
            ),
        ]
        if self.encryption.kind is EncryptionKind.LUKS2:
            cmds.append(
                Command(
                    argv=(
                        "sh",
                        "-c",
                        (f"printf 'GRUB_ENABLE_CRYPTODISK=y\\n' >> {defaults_path}"),
                    ),
                    description="enable cryptodisk in /etc/default/grub",
                ),
            )
        cmds.append(
            Command(
                argv=("grub-mkconfig", "-o", "/boot/grub/grub.cfg"),
                chroot=True,
                description="render /boot/grub/grub.cfg",
            ),
        )
        return tuple(cmds)

    def _cmdline(self) -> str:
        params: list[str] = []
        if self.encryption.kind is EncryptionKind.LUKS2:
            cryptdevice = f"cryptdevice={self.crypt_partition_path}:{self.encryption.mapper_name}"
            if self.encryption.header_path:
                cryptdevice = f"{cryptdevice}:header={self.encryption.header_path}"
            params.append(cryptdevice)
            root = self.root_device or f"/dev/mapper/{self.encryption.mapper_name}"
            params.append(f"root={root}")
            luks_options: list[str] = []
            if self.encryption.header_path:
                luks_options.append(f"header={self.encryption.header_path}")
            if luks_options:
                params.append(f"rd.luks.options={','.join(luks_options)}")
        else:
            params.append(f"root=LABEL={self.root_label}")
        if self.rootflags:
            params.append(self.rootflags)
        params.append("rw")
        params.extend(self.spec.extra_kernel_params)
        return " ".join(params)


def build_bootloader_strategy(
    spec: BootloaderSpec,
    *,
    kernel: KernelSpec,
    microcode: MicrocodeKind,
    encryption: EncryptionSpec,
    rootflags: str | None,
    crypt_partition_path: str,
    mount_root: Path,
    root_device: str = "",
    root_label: str = "system",
) -> SystemdBootStrategy | GrubStrategy | UkiStrategy:
    common: dict[str, object] = {
        "spec": spec,
        "kernel": kernel,
        "microcode": microcode,
        "encryption": encryption,
        "rootflags": rootflags,
        "crypt_partition_path": crypt_partition_path,
        "mount_root": mount_root,
        "root_device": root_device,
        "root_label": root_label,
    }
    if spec.kind is BootloaderKind.SYSTEMD_BOOT:
        return SystemdBootStrategy(**common)  # type: ignore[arg-type]
    if spec.kind is BootloaderKind.GRUB:
        return GrubStrategy(**common)  # type: ignore[arg-type]
    if spec.kind is BootloaderKind.UKI:
        return UkiStrategy(**common)  # type: ignore[arg-type]
    raise ValueError(f"unsupported bootloader kind: {spec.kind!r}")
