"""Regression: dracut renders quirk-supplied kernel drivers via force_drivers.

Codex P6 finding: ``DracutStrategy`` previously concatenated quirks
into ``add_dracutmodules`` (the dracut module namespace). Quirks
contribute *kernel driver* names (e.g. ``tpm_tis``); pushing them
into the dracut module list is a silent contract violation that can
omit the early driver from the initramfs.
"""

from __future__ import annotations

from pathlib import Path

from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.kernel import KernelKind, KernelSpec
from getarch.domain.secret import Secret
from getarch.planning.strategies.initramfs import (
    DracutStrategy,
    MkinitcpioStrategy,
)


def test_mkinitcpio_modules_render_into_modules_block() -> None:
    cmds = MkinitcpioStrategy(
        hooks=("base", "udev"),
        kernel=KernelSpec(kind=KernelKind("linux")),
        mount_root=Path("/mnt"),
        extra_modules=("tpm_tis",),
    ).commands()
    snippet = cmds[0].input or ""
    assert "MODULES=(tpm_tis)" in snippet
    assert "HOOKS=(base udev)" in snippet


def test_dracut_quirk_modules_use_force_drivers_not_modules() -> None:
    cmds = DracutStrategy(
        kernel=KernelSpec(kind=KernelKind("linux")),
        encryption=EncryptionSpec(
            kind=EncryptionKind.LUKS2,
            mapper_name="system",
            password=Secret("x"),
        ),
        mount_root=Path("/mnt"),
        extra_modules=("tpm_tis",),
    ).commands()
    conf = cmds[0].input or ""
    # Quirk-supplied kernel drivers MUST land in force_drivers.
    assert "force_drivers+=\" tpm_tis \"" in conf
    # And MUST NOT be smuggled into the dracut module list.
    add_modules_line = next(
        line for line in conf.splitlines() if line.startswith("add_dracutmodules+=")
    )
    assert "tpm_tis" not in add_modules_line


def test_dracut_without_quirks_omits_force_drivers_line() -> None:
    cmds = DracutStrategy(
        kernel=KernelSpec(kind=KernelKind("linux")),
        encryption=EncryptionSpec(kind=EncryptionKind.NONE, mapper_name="system"),
        mount_root=Path("/mnt"),
    ).commands()
    conf = cmds[0].input or ""
    assert "force_drivers" not in conf
