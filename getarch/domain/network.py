"""Network value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from getarch.domain.locale import Hostname


class NetworkBackend(StrEnum):
    NETWORK_MANAGER = "networkmanager"
    SYSTEMD_NETWORKD = "systemd-networkd"
    IWD = "iwd"


@dataclass(frozen=True, slots=True)
class HostsEntry:
    address: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NetworkSpec:
    backend: NetworkBackend = NetworkBackend.NETWORK_MANAGER
    hostname: Hostname | None = None
    extra_packages: tuple[str, ...] = field(default_factory=tuple)

    def default_hosts_entries(self) -> tuple[HostsEntry, ...]:
        host = self.hostname.value if self.hostname else "arch"
        return (
            HostsEntry("127.0.0.1", ("localhost",)),
            HostsEntry("::1", ("localhost",)),
            HostsEntry("127.0.1.1", (f"{host}.localdomain", host)),
        )
