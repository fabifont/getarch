import pytest

from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.secret import Secret


def test_none_does_not_require_password() -> None:
    EncryptionSpec(kind=EncryptionKind.NONE)


def test_luks2_requires_password() -> None:
    with pytest.raises(ValueError, match="password"):
        EncryptionSpec(kind=EncryptionKind.LUKS2)


def test_luks2_accepts_password() -> None:
    spec = EncryptionSpec(kind=EncryptionKind.LUKS2, password=Secret("p"), mapper_name="system")
    assert spec.mapper_name == "system"


def test_luks2_default_mapper_name() -> None:
    spec = EncryptionSpec(kind=EncryptionKind.LUKS2, password=Secret("p"))
    assert spec.mapper_name == "system"
