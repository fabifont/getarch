from pathlib import Path

from getarch.planning.strategies.swap import SwapfileStrategy, ZramStrategy


def test_ext4_swapfile_no_chattr() -> None:
    strat = SwapfileStrategy(size_mib=2048, mount_root=Path("/mnt"), btrfs=False)
    argvs = [c.argv for c in strat.commands()]
    assert ("mkdir", "-p", "/mnt/swap") in argvs
    assert all("chattr" not in a[0] for a in argvs)
    assert ("fallocate", "-l", "2048MiB", "/mnt/swap/swapfile") in argvs
    assert ("chmod", "600", "/mnt/swap/swapfile") in argvs
    assert ("mkswap", "/mnt/swap/swapfile") in argvs
    assert ("swapon", "/mnt/swap/swapfile") in argvs


def test_btrfs_swapfile_chattr_first() -> None:
    strat = SwapfileStrategy(size_mib=2048, mount_root=Path("/mnt"), btrfs=True)
    argvs = [c.argv for c in strat.commands()]
    mkdir_idx = argvs.index(("mkdir", "-p", "/mnt/swap"))
    chattr_idx = argvs.index(("chattr", "+C", "/mnt/swap"))
    fallocate_idx = next(i for i, a in enumerate(argvs) if a[0] == "fallocate")
    assert mkdir_idx < chattr_idx < fallocate_idx


def test_zram_writes_generator_conf_with_size() -> None:
    strat = ZramStrategy(mount_root=Path("/mnt"), size_mib=4096)
    cmds = strat.commands()
    assert len(cmds) == 1
    assert cmds[0].argv == (
        "install",
        "-Dm644",
        "/dev/stdin",
        "/mnt/etc/systemd/zram-generator.conf",
    )
    assert "zram-size = 4096MiB" in (cmds[0].input or "")


def test_zram_default_size_uses_min_ram() -> None:
    strat = ZramStrategy(mount_root=Path("/mnt"))
    cmds = strat.commands()
    assert "zram-size = min(ram, 8192)" in (cmds[0].input or "")
