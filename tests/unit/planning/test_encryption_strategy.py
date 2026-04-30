from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.domain.secret import Secret
from getarch.planning.strategies.encryption import (
    build_encryption_strategy,
)


def test_no_encryption_strategy_emits_zero_commands() -> None:
    spec = EncryptionSpec(kind=EncryptionKind.NONE)
    assert build_encryption_strategy(spec).commands() == ()


def test_luks_strategy_format_and_open() -> None:
    spec = EncryptionSpec(kind=EncryptionKind.LUKS2, password=Secret("p"), mapper_name="system")
    cmds = build_encryption_strategy(spec).commands()
    assert any("luksFormat" in arg for c in cmds for arg in c.argv)
    assert any("open" in arg for c in cmds for arg in c.argv)
    assert all(c.sensitive for c in cmds)
