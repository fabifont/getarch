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


def test_luks_with_tpm2_emits_systemd_cryptenroll() -> None:
    spec = EncryptionSpec(
        kind=EncryptionKind.LUKS2,
        password=Secret("p"),
        tpm2_unlock=True,
    )
    cmds = build_encryption_strategy(spec).commands()
    enroll = next(c for c in cmds if c.argv[0] == "systemd-cryptenroll")
    assert "--tpm2-device=auto" in enroll.argv


def test_luks_with_fido2_emits_systemd_cryptenroll() -> None:
    spec = EncryptionSpec(
        kind=EncryptionKind.LUKS2,
        password=Secret("p"),
        fido2_unlock=True,
    )
    cmds = build_encryption_strategy(spec).commands()
    enroll = next(c for c in cmds if c.argv[0] == "systemd-cryptenroll")
    assert "--fido2-device=auto" in enroll.argv


def test_luks_with_detached_header_passes_header_arg() -> None:
    spec = EncryptionSpec(
        kind=EncryptionKind.LUKS2,
        password=Secret("p"),
        header_path="/run/cryptheader",
    )
    cmds = build_encryption_strategy(spec).commands()
    for c in cmds[:2]:
        assert "--header" in c.argv
        assert "/run/cryptheader" in c.argv
