from pathlib import Path

from getarch.domain.bootloader import BootloaderKind, BootloaderSpec
from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.kernel import KernelKind, KernelSpec, MicrocodeKind
from getarch.domain.secret import Secret
from getarch.planning.strategies.bootloader import SystemdBootStrategy


def test_bootctl_runs_outside_chroot_with_esp_path() -> None:
    cmds = SystemdBootStrategy(
        spec=BootloaderSpec(kind=BootloaderKind.SYSTEMD_BOOT, entry_id="arch", timeout_seconds=3),
        kernel=KernelSpec(kind=KernelKind.LINUX),
        microcode=MicrocodeKind.INTEL,
        encryption=EncryptionSpec(kind=EncryptionKind.NONE),
        rootflags=None,
        crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
        mount_root=Path("/mnt"),
    ).commands()
    bootctl = next(c for c in cmds if c.argv[0] == "bootctl")
    assert bootctl.chroot is False
    assert bootctl.argv == ("bootctl", "--esp-path=/mnt/boot", "install")


def test_non_luks_entry_uses_label_and_no_bash() -> None:
    cmds = SystemdBootStrategy(
        spec=BootloaderSpec(),
        kernel=KernelSpec(),
        microcode=MicrocodeKind.NONE,
        encryption=EncryptionSpec(kind=EncryptionKind.NONE),
        rootflags=None,
        crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
        mount_root=Path("/mnt"),
    ).commands()
    assert "bash" not in [c.argv[0] for c in cmds]
    flat = " ".join(arg for c in cmds for arg in c.argv) + " ".join(c.input or "" for c in cmds)
    assert "root=LABEL=system" in flat
    entry_cmd = next(
        c
        for c in cmds
        if c.argv[:3] == ("install", "-Dm644", "/dev/stdin") and "entries" in c.argv[3]
    )
    assert entry_cmd.input is not None
    assert "linux /vmlinuz-linux" in entry_cmd.input


def test_luks_entry_uses_bash_with_blkid_substitution() -> None:
    cmds = SystemdBootStrategy(
        spec=BootloaderSpec(),
        kernel=KernelSpec(),
        microcode=MicrocodeKind.NONE,
        encryption=EncryptionSpec(kind=EncryptionKind.LUKS2, password=Secret("x")),
        rootflags=None,
        crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
        mount_root=Path("/mnt"),
    ).commands()
    bash_cmd = next(c for c in cmds if c.argv[0] == "bash")
    assert bash_cmd.argv[1] == "-c"
    script = bash_cmd.argv[2]
    assert "blkid -s UUID -o value /dev/disk/by-partlabel/cryptsystem" in script
    assert "rd.luks.name=${LUKS_UUID}=system" in script
    assert "root=/dev/mapper/system" in script


def test_btrfs_includes_rootflags() -> None:
    cmds = SystemdBootStrategy(
        spec=BootloaderSpec(),
        kernel=KernelSpec(),
        microcode=MicrocodeKind.NONE,
        encryption=EncryptionSpec(kind=EncryptionKind.NONE),
        rootflags="rootflags=subvol=@",
        crypt_partition_path="/dev/disk/by-partlabel/cryptsystem",
        mount_root=Path("/mnt"),
    ).commands()
    flat = " ".join(arg for c in cmds for arg in c.argv) + " ".join(c.input or "" for c in cmds)
    assert "rootflags=subvol=@" in flat
