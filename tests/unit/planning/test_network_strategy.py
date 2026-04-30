from pathlib import Path

from getarch.planning.strategies.network import (
    IwdNetworkPlan,
    NetworkConfigStrategy,
    NetworkdProfilePlan,
)


def test_networkd_profile_renders_ini() -> None:
    strat = NetworkConfigStrategy(
        backend="systemd-networkd",
        networkd_profiles=(
            NetworkdProfilePlan(
                name="20-wired",
                match={"Name": "en*"},
                network={"DHCP": "yes", "DNS": ["1.1.1.1", "8.8.8.8"]},
            ),
        ),
        iwd_networks=(),
        mount_root=Path("/mnt"),
    )
    cmds = strat.commands()
    assert len(cmds) == 1
    assert cmds[0].argv == (
        "install",
        "-Dm644",
        "/dev/stdin",
        "/mnt/etc/systemd/network/20-wired.network",
    )
    txt = cmds[0].input or ""
    assert "[Match]" in txt
    assert "Name=en*" in txt
    assert "[Network]" in txt
    assert "DHCP=yes" in txt
    assert "DNS=1.1.1.1" in txt
    assert "DNS=8.8.8.8" in txt


def test_iwd_psk_file_is_sensitive() -> None:
    strat = NetworkConfigStrategy(
        backend="iwd",
        networkd_profiles=(),
        iwd_networks=(IwdNetworkPlan(ssid="MyWifi", psk="secret"),),
        mount_root=Path("/mnt"),
    )
    cmds = strat.commands()
    assert len(cmds) == 1
    cmd = cmds[0]
    assert cmd.sensitive is True
    assert cmd.argv == (
        "install",
        "-Dm600",
        "/dev/stdin",
        "/mnt/var/lib/iwd/MyWifi.psk",
    )
    assert "Passphrase = secret" in (cmd.input or "")


def test_networkmanager_backend_emits_nothing() -> None:
    strat = NetworkConfigStrategy(
        backend="networkmanager",
        networkd_profiles=(),
        iwd_networks=(),
        mount_root=Path("/mnt"),
    )
    assert strat.commands() == ()
