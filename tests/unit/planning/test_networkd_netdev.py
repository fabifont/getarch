from copy import deepcopy
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner
from getarch.planning.strategies.network import (
    NetworkConfigStrategy,
    NetworkdLinkPlan,
    NetworkdNetdevPlan,
    NetworkdProfilePlan,
)


def _strategy(**overrides: object) -> NetworkConfigStrategy:
    base: dict[str, object] = {
        "backend": "systemd-networkd",
        "networkd_profiles": (),
        "networkd_netdevs": (),
        "networkd_links": (),
        "iwd_networks": (),
        "mount_root": Path("/mnt"),
    }
    base.update(overrides)
    return NetworkConfigStrategy(**base)  # type: ignore[arg-type]


def test_vlan_netdev_renders_id_into_vlan_section() -> None:
    cmds = _strategy(
        networkd_netdevs=(
            NetworkdNetdevPlan(
                name="vlan100",
                kind="vlan",
                properties={"Id": "100", "Protocol": "802.1Q"},
            ),
        ),
    ).commands()
    assert len(cmds) == 1
    body = cmds[0].input or ""
    assert cmds[0].argv[-1] == "/mnt/etc/systemd/network/vlan100.netdev"
    assert "[NetDev]" in body
    assert "Name=vlan100" in body
    assert "Kind=vlan" in body
    assert "[VLAN]" in body
    assert "Id=100" in body
    assert "Protocol=802.1Q" in body


def test_bridge_netdev_routes_priority_to_bridge_section() -> None:
    cmds = _strategy(
        networkd_netdevs=(
            NetworkdNetdevPlan(
                name="br0",
                kind="bridge",
                properties={"STP": "true", "Priority": "32768"},
            ),
        ),
    ).commands()
    body = cmds[0].input or ""
    assert "[Bridge]" in body
    assert "STP=true" in body
    assert "Priority=32768" in body


def test_bond_netdev_routes_mode_to_bond_section() -> None:
    cmds = _strategy(
        networkd_netdevs=(
            NetworkdNetdevPlan(
                name="bond0",
                kind="bond",
                properties={
                    "Mode": "802.3ad",
                    "TransmitHashPolicy": "layer3+4",
                    "MIIMonitorSec": "1s",
                },
            ),
        ),
    ).commands()
    body = cmds[0].input or ""
    assert "[Bond]" in body
    assert "Mode=802.3ad" in body
    assert "TransmitHashPolicy=layer3+4" in body
    assert "MIIMonitorSec=1s" in body


def test_unknown_property_falls_back_to_netdev_section() -> None:
    cmds = _strategy(
        networkd_netdevs=(
            NetworkdNetdevPlan(
                name="vlan10",
                kind="vlan",
                properties={"MTUBytes": "9000"},
            ),
        ),
    ).commands()
    body = cmds[0].input or ""
    # MTUBytes is a [NetDev]-section key; should not land in [VLAN].
    netdev_block, _, vlan_block = body.partition("[VLAN]")
    assert "MTUBytes=9000" in netdev_block
    assert "MTUBytes" not in vlan_block


def test_link_renders_match_and_link_sections() -> None:
    cmds = _strategy(
        networkd_links=(
            NetworkdLinkPlan(
                name="10-naming",
                match={"OriginalName": "enp*"},
                link={"NamePolicy": "kernel", "MACAddressPolicy": "persistent"},
            ),
        ),
    ).commands()
    assert cmds[0].argv[-1] == "/mnt/etc/systemd/network/10-naming.link"
    body = cmds[0].input or ""
    assert "[Match]" in body
    assert "OriginalName=enp*" in body
    assert "[Link]" in body
    assert "NamePolicy=kernel" in body


def test_planner_renders_netdev_alongside_network() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["network"] = {
        "hostname": "h",
        "backend": "systemd-networkd",
        "systemd_networkd": [
            {
                "name": "20-vlan100",
                "match": {"Name": "vlan100"},
                "network": {"DHCP": "ipv4"},
            },
        ],
        "systemd_networkd_netdevs": [
            {
                "name": "vlan100",
                "kind": "vlan",
                "properties": {"Id": "100"},
            },
        ],
    }
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    netcfg = next(s for s in plan.steps if s.id == "network-config")
    targets = [c.argv[-1] for c in netcfg.commands]
    assert "/mnt/etc/systemd/network/20-vlan100.network" in targets
    assert "/mnt/etc/systemd/network/vlan100.netdev" in targets


def test_strategy_emits_no_commands_for_networkmanager_backend() -> None:
    cmds = _strategy(
        backend="networkmanager",
        networkd_netdevs=(NetworkdNetdevPlan(name="x", kind="vlan", properties={}),),
    ).commands()
    assert cmds == ()


def test_planner_omits_step_when_no_netdev_or_profile() -> None:
    # Existing behavior still holds: backend!=networkmanager but no profiles
    # and no netdevs → no network-config step.
    cmd_keep = NetworkdProfilePlan(name="x", match={}, network={})
    assert cmd_keep.name == "x"
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["network"] = {"hostname": "h", "backend": "systemd-networkd"}
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    assert all(s.id != "network-config" for s in plan.steps)
