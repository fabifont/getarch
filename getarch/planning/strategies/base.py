"""Strategy protocols: each returns the commands needed for its concern."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from getarch.execution.command import Command


@runtime_checkable
class _CommandProducing(Protocol):
    def commands(self) -> tuple[Command, ...]: ...


PartitioningStrategy = _CommandProducing
EncryptionStrategy = _CommandProducing
FilesystemStrategy = _CommandProducing
BootloaderStrategy = _CommandProducing
InitramfsStrategy = _CommandProducing
