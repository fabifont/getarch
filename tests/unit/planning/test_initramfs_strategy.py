from pathlib import Path

from getarch.domain.kernel import KernelKind, KernelSpec
from getarch.planning.strategies.initramfs import MkinitcpioStrategy


def test_writes_hooks_and_runs_mkinitcpio() -> None:
    cmds = MkinitcpioStrategy(
        hooks=("base", "udev", "autodetect", "modconf", "block", "filesystems", "fsck"),
        kernel=KernelSpec(kind=KernelKind.LINUX),
        mount_root=Path("/mnt"),
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv) + " ".join(c.input or "" for c in cmds)
    assert "/mnt/etc/mkinitcpio.conf.d/10-hooks.conf" in flat
    assert "mkinitcpio" in flat
    assert "linux" in flat


def test_lts_kernel_uses_lts_preset() -> None:
    cmds = MkinitcpioStrategy(
        hooks=("base", "udev"),
        kernel=KernelSpec(kind=KernelKind.LTS),
        mount_root=Path("/mnt"),
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv)
    assert "linux-lts" in flat
