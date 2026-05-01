"""systemd-networkd and iwd configuration files."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class NetworkdProfilePlan:
    name: str
    match: dict[str, str]
    network: dict[str, str | list[str]]


@dataclass(frozen=True, slots=True)
class NetworkdNetdevPlan:
    name: str
    kind: str
    properties: dict[str, str]


@dataclass(frozen=True, slots=True)
class NetworkdLinkPlan:
    name: str
    match: dict[str, str]
    link: dict[str, str | list[str]]


@dataclass(frozen=True, slots=True)
class IwdNetworkPlan:
    ssid: str
    psk: str


# systemd.netdev(5) — keys whose home is the kind-specific section
# rather than [NetDev]. Anything not listed here lands in [NetDev].
_VLAN_KEYS = frozenset({
    "Id", "Protocol", "GVRP", "MVRP", "LooseBinding", "ReorderHeader",
    "EgressQOSMaps", "IngressQOSMaps",
})
_BRIDGE_KEYS = frozenset({
    "HelloTimeSec", "MaxAgeSec", "ForwardDelaySec", "AgeingTimeSec",
    "Priority", "GroupForwardMask", "DefaultPVID", "MulticastQuerier",
    "MulticastSnooping", "VLANFiltering", "VLANProtocol", "STP",
    "MulticastIGMPVersion",
})
_BOND_KEYS = frozenset({
    "Mode", "TransmitHashPolicy", "LACPTransmitRate", "MIIMonitorSec",
    "UpDelaySec", "DownDelaySec", "GratuitousARP", "AllSlavesActive",
    "DynamicTransmitLoadBalancing", "MinLinks", "AdSelect",
    "FailOverMACPolicy", "ARPValidate", "ARPIntervalSec", "ARPIPTargets",
    "ARPAllTargets", "PrimaryReselectPolicy", "ResendIGMP",
    "PacketsPerSlave", "NumberOfARPTargets", "ActiveSlave", "PrimarySlave",
})
_NETDEV_KIND_SECTION_KEYS: dict[str, frozenset[str]] = {
    "vlan": _VLAN_KEYS,
    "bridge": _BRIDGE_KEYS,
    "bond": _BOND_KEYS,
}


@dataclass(frozen=True, slots=True)
class NetworkConfigStrategy:
    backend: str
    networkd_profiles: tuple[NetworkdProfilePlan, ...]
    iwd_networks: tuple[IwdNetworkPlan, ...]
    mount_root: Path
    networkd_netdevs: tuple[NetworkdNetdevPlan, ...] = ()
    networkd_links: tuple[NetworkdLinkPlan, ...] = ()

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = []
        if self.backend == "systemd-networkd":
            cmds.extend(self._networkd_commands())
            cmds.extend(self._netdev_commands())
            cmds.extend(self._link_commands())
        if self.backend == "iwd":
            cmds.extend(self._iwd_commands())
        return tuple(cmds)

    def _networkd_commands(self) -> Iterable[Command]:
        for profile in self.networkd_profiles:
            target = (
                self.mount_root
                / "etc/systemd/network"
                / f"{profile.name}.network"
            )
            yield Command(
                argv=("install", "-Dm644", "/dev/stdin", str(target)),
                input=_render_ini(
                    [("Match", profile.match), ("Network", profile.network)],
                ),
                description=f"write {target}",
            )

    def _netdev_commands(self) -> Iterable[Command]:
        for nd in self.networkd_netdevs:
            target = (
                self.mount_root
                / "etc/systemd/network"
                / f"{nd.name}.netdev"
            )
            kind_section_name = nd.kind.upper() if nd.kind == "vlan" else nd.kind.capitalize()
            kind_keys = _NETDEV_KIND_SECTION_KEYS.get(nd.kind, frozenset())
            netdev_section: dict[str, str | list[str]] = {
                "Name": nd.name,
                "Kind": nd.kind,
            }
            kind_section: dict[str, str | list[str]] = {}
            for key, value in nd.properties.items():
                if key in kind_keys:
                    kind_section[key] = value
                else:
                    netdev_section[key] = value
            yield Command(
                argv=("install", "-Dm644", "/dev/stdin", str(target)),
                input=_render_ini(
                    [("NetDev", netdev_section), (kind_section_name, kind_section)],
                ),
                description=f"write {target}",
            )

    def _link_commands(self) -> Iterable[Command]:
        for link in self.networkd_links:
            target = (
                self.mount_root
                / "etc/systemd/network"
                / f"{link.name}.link"
            )
            yield Command(
                argv=("install", "-Dm644", "/dev/stdin", str(target)),
                input=_render_ini(
                    [("Match", link.match), ("Link", link.link)],
                ),
                description=f"write {target}",
            )

    def _iwd_commands(self) -> Iterable[Command]:
        for net in self.iwd_networks:
            target = self.mount_root / "var/lib/iwd" / f"{net.ssid}.psk"
            yield Command(
                argv=("install", "-Dm600", "/dev/stdin", str(target)),
                input=f"[Security]\nPassphrase = {net.psk}\n",
                sensitive=True,
                description=f"write {target}",
            )


def _render_ini(sections: list[tuple[str, Mapping[str, str | list[str]]]]) -> str:
    out: list[str] = []
    for name, kvs in sections:
        if not kvs:
            continue
        out.append(f"[{name}]")
        for key, value in kvs.items():
            if isinstance(value, list):
                for item in value:
                    out.append(f"{key}={item}")
            else:
                out.append(f"{key}={value}")
        out.append("")
    return "\n".join(out)
