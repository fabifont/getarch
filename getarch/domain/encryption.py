"""Encryption value objects (LUKS2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from getarch.domain.secret import Secret


class EncryptionKind(StrEnum):
    NONE = "none"
    LUKS2 = "luks2"


@dataclass(frozen=True, slots=True)
class EncryptionSpec:
    kind: EncryptionKind = EncryptionKind.NONE
    password: Secret | None = None
    mapper_name: str = "system"
    tpm2_unlock: bool = False
    fido2_unlock: bool = False
    header_path: str | None = None

    def __post_init__(self) -> None:
        if self.kind is EncryptionKind.LUKS2 and self.password is None:
            raise ValueError("LUKS2 encryption requires a password")
        if self.tpm2_unlock and self.fido2_unlock:
            raise ValueError("set at most one of tpm2_unlock or fido2_unlock")
