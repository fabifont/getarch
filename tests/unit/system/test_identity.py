import pytest

from getarch.system.identity import OsIdentity


def test_is_root_reads_geteuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.geteuid", lambda: 0)
    assert OsIdentity().is_root() is True


def test_is_root_false_when_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    assert OsIdentity().is_root() is False
