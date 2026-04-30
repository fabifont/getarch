import socket

import pytest

from getarch.system.network import SocketNetwork


def test_reachable_when_getaddrinfo_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake(host: str, port: object, *args: object, **kwargs: object) -> list[object]:
        captured["host"] = host
        return [("af", "type", "proto", "canon", ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert SocketNetwork().internet_reachable("archlinux.org") is True
    assert captured["host"] == "archlinux.org"


def test_unreachable_when_gaierror(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(host: str, port: object, *args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror(-2, "name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert SocketNetwork().internet_reachable("archlinux.org") is False


def test_unreachable_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(host: str, port: object, *args: object, **kwargs: object) -> list[object]:
        raise TimeoutError

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert SocketNetwork().internet_reachable("archlinux.org") is False
