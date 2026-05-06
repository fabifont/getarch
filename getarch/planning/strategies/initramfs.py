"""Initramfs generation strategies (mkinitcpio, dracut)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.kernel import KernelSpec
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class MkinitcpioStrategy:
    hooks: tuple[str, ...]
    kernel: KernelSpec
    mount_root: Path
    extra_modules: tuple[str, ...] = ()

    def commands(self) -> tuple[Command, ...]:
        snippet_path = self.mount_root / "etc/mkinitcpio.conf.d/10-hooks.conf"
        hooks_text = f"HOOKS=({' '.join(self.hooks)})\n"
        if self.extra_modules:
            hooks_text += f"MODULES=({' '.join(self.extra_modules)})\n"
        return (
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(snippet_path)),
                input=hooks_text,
                description=f"write mkinitcpio hooks snippet at {snippet_path}",
            ),
            Command(
                argv=("mkinitcpio", "-p", self.kernel.kind.value),
                chroot=True,
                description=f"regenerate initramfs for {self.kernel.kind.value}",
            ),
        )


@dataclass(frozen=True, slots=True)
class DracutStrategy:
    """Generate the initramfs with dracut.

    Writes a small drop-in to ``/etc/dracut.conf.d/10-getarch.conf`` and runs
    ``dracut --regenerate-all --force`` inside the chroot.

    For LUKS2 setups, dracut auto-discovers the encrypted root from the
    kernel cmdline (``rd.luks.uuid``/``rd.luks.name``) emitted by the
    bootloader strategy.
    """

    kernel: KernelSpec
    encryption: EncryptionSpec
    mount_root: Path
    extra_modules: tuple[str, ...] = ()

    def commands(self) -> tuple[Command, ...]:
        conf_path = self.mount_root / "etc/dracut.conf.d/10-getarch.conf"
        # `add_dracutmodules` lists *dracut* modules (e.g. `crypt`,
        # `systemd`) — they're not the same namespace as kernel
        # drivers. Quirks contribute kernel drivers (e.g. `tpm_tis`),
        # which dracut handles via `force_drivers` to ensure they're
        # installed in the initramfs even if dracut wouldn't pick them
        # up by autodetection.
        modules: list[str] = ["base", "systemd", "fs-lib"]
        if self.encryption.kind is EncryptionKind.LUKS2:
            modules.append("crypt")
        conf_lines = [
            "hostonly=yes",
            f'add_dracutmodules+=" {" ".join(modules)} "',
            "compress=zstd",
        ]
        if self.extra_modules:
            conf_lines.append(
                f'force_drivers+=" {" ".join(self.extra_modules)} "',
            )
        conf_text = "\n".join(conf_lines) + "\n"
        return (
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(conf_path)),
                input=conf_text,
                description=f"write dracut config at {conf_path}",
            ),
            Command(
                argv=("dracut", "--regenerate-all", "--force"),
                chroot=True,
                description="regenerate all initramfs images via dracut",
            ),
        )


def build_initramfs_strategy(
    *,
    generator: str,
    hooks: tuple[str, ...],
    kernel: KernelSpec,
    encryption: EncryptionSpec,
    mount_root: Path,
    extra_modules: tuple[str, ...] = (),
) -> MkinitcpioStrategy | DracutStrategy:
    if generator == "mkinitcpio":
        return MkinitcpioStrategy(
            hooks=hooks,
            kernel=kernel,
            mount_root=mount_root,
            extra_modules=extra_modules,
        )
    if generator == "dracut":
        return DracutStrategy(
            kernel=kernel,
            encryption=encryption,
            mount_root=mount_root,
            extra_modules=extra_modules,
        )
    raise ValueError(f"unsupported initramfs generator: {generator!r}")
