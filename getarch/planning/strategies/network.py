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
class IwdNetworkPlan:
    ssid: str
    psk: str


@dataclass(frozen=True, slots=True)
class NetworkConfigStrategy:
    backend: str
    networkd_profiles: tuple[NetworkdProfilePlan, ...]
    iwd_networks: tuple[IwdNetworkPlan, ...]
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        cmds: list[Command] = []
        if self.backend == "systemd-networkd":
            cmds.extend(self._networkd_commands())
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
