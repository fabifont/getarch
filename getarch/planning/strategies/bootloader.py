"""systemd-boot bootloader strategy.

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

from getarch.domain.bootloader import BootloaderSpec
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
            params.append("rd.luks.options=discard")
            params.append(f"root=/dev/mapper/{self.encryption.mapper_name}")
        else:
            params.append("root=LABEL=system")
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
