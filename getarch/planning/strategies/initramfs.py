"""mkinitcpio initramfs strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.domain.kernel import KernelSpec
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class MkinitcpioStrategy:
    hooks: tuple[str, ...]
    kernel: KernelSpec
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        snippet_path = self.mount_root / "etc/mkinitcpio.conf.d/10-hooks.conf"
        hooks_text = f"HOOKS=({' '.join(self.hooks)})\n"
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
