from getarch.execution.command import Command
from getarch.planning.strategies.base import (
    BootloaderStrategy,
    EncryptionStrategy,
    FilesystemStrategy,
    InitramfsStrategy,
    PartitioningStrategy,
)


class _Stub:
    def commands(self) -> tuple[Command, ...]:
        return (Command(argv=("true",)),)


def test_protocols_satisfied_by_stub() -> None:
    p: PartitioningStrategy = _Stub()
    e: EncryptionStrategy = _Stub()
    f: FilesystemStrategy = _Stub()
    b: BootloaderStrategy = _Stub()
    i: InitramfsStrategy = _Stub()
    for s in (p, e, f, b, i):
        assert s.commands()
