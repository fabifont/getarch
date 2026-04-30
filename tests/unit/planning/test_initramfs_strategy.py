from pathlib import Path

from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.kernel import KernelKind, KernelSpec
from getarch.domain.secret import Secret
from getarch.planning.strategies.initramfs import (
    DracutStrategy,
    MkinitcpioStrategy,
    build_initramfs_strategy,
)


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


def test_dracut_writes_conf_and_runs_regenerate() -> None:
    cmds = DracutStrategy(
        kernel=KernelSpec(kind=KernelKind.LINUX),
        encryption=EncryptionSpec(kind=EncryptionKind.NONE),
        mount_root=Path("/mnt"),
    ).commands()
    argvs = [c.argv for c in cmds]
    assert ("dracut", "--regenerate-all", "--force") in argvs
    flat = "".join(c.input or "" for c in cmds)
    assert "/mnt/etc/dracut.conf.d/10-getarch.conf" in " ".join(
        arg for c in cmds for arg in c.argv
    )
    assert "hostonly=yes" in flat


def test_dracut_with_luks_adds_crypt_module() -> None:
    cmds = DracutStrategy(
        kernel=KernelSpec(),
        encryption=EncryptionSpec(kind=EncryptionKind.LUKS2, password=Secret("x")),
        mount_root=Path("/mnt"),
    ).commands()
    flat = "".join(c.input or "" for c in cmds)
    assert "crypt" in flat


def test_initramfs_factory_dispatches() -> None:
    encryption = EncryptionSpec(kind=EncryptionKind.NONE)
    mki = build_initramfs_strategy(
        generator="mkinitcpio",
        hooks=("base", "udev"),
        kernel=KernelSpec(),
        encryption=encryption,
        mount_root=Path("/mnt"),
    )
    drc = build_initramfs_strategy(
        generator="dracut",
        hooks=(),
        kernel=KernelSpec(),
        encryption=encryption,
        mount_root=Path("/mnt"),
    )
    assert isinstance(mki, MkinitcpioStrategy)
    assert isinstance(drc, DracutStrategy)
