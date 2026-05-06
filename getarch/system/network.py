"""Network reachability check used by environment preflight."""

from __future__ import annotations

import socket
from dataclasses import dataclass

from getarch.constants import INTERNET_REACHABILITY_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class SocketNetwork:
    timeout_seconds: float = INTERNET_REACHABILITY_TIMEOUT_SECONDS

    def internet_reachable(self, host: str) -> bool:
        previous = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(self.timeout_seconds)
            try:
                socket.getaddrinfo(host, None)
            except socket.gaierror, OSError, TimeoutError:
                return False
            return True
        finally:
            socket.setdefaulttimeout(previous)
