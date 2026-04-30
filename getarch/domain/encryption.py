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

    def __post_init__(self) -> None:
        if self.kind is EncryptionKind.LUKS2 and self.password is None:
            raise ValueError("LUKS2 encryption requires a password")
