"""Discovery protocols. Implementations live in sibling modules."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from getarch.domain.disk import Disk


@runtime_checkable
class BlockDeviceProvider(Protocol):
    def list_disks(self) -> tuple[Disk, ...]: ...


@runtime_checkable
class EnvironmentProvider(Protocol):
    def cpu_vendor(self) -> str | None: ...
    def supported_locales(self) -> tuple[str, ...]: ...
    def keymaps(self) -> tuple[str, ...]: ...
    def timezones(self) -> tuple[str, ...]: ...


@runtime_checkable
class FirmwareProvider(Protocol):
    def is_uefi(self) -> bool: ...


@runtime_checkable
class PacmanProvider(Protocol):
    def package_exists(self, name: str) -> bool: ...


@runtime_checkable
class IdentityProvider(Protocol):
    def is_root(self) -> bool: ...
