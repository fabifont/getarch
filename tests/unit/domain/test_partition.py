import pytest

from getarch.domain.partition import ByteSize, PartitionRole, PartitionSpec


def test_bytesize_from_mib() -> None:
    assert ByteSize.from_mib(1).bytes == 1024 * 1024


def test_bytesize_from_gib() -> None:
    assert ByteSize.from_gib(2).bytes == 2 * 1024 * 1024 * 1024


def test_bytesize_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ByteSize(bytes=0)


def test_partitionspec_efi_requires_size() -> None:
    PartitionSpec(role=PartitionRole.EFI, size=ByteSize.from_mib(512))
    with pytest.raises(ValueError):
        PartitionSpec(role=PartitionRole.EFI, size=None)


def test_partitionspec_root_can_use_rest() -> None:
    PartitionSpec(role=PartitionRole.ROOT, size=None)
