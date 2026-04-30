from getarch.domain.locale import Hostname
from getarch.domain.network import HostsEntry, NetworkBackend, NetworkSpec


def test_default_network_uses_networkmanager() -> None:
    assert NetworkSpec().backend is NetworkBackend.NETWORK_MANAGER


def test_hosts_entry_default_127001_lines() -> None:
    spec = NetworkSpec(hostname=Hostname("arch"))
    entries = spec.default_hosts_entries()
    assert HostsEntry(address="127.0.0.1", names=("localhost",)) in entries
    assert any("arch" in e.names for e in entries)
