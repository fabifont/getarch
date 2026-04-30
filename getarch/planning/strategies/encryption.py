"""LUKS2 encryption strategies."""

from __future__ import annotations

from dataclasses import dataclass

from getarch.domain.encryption import EncryptionKind, EncryptionSpec
from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class NoEncryptionStrategy:
    def commands(self) -> tuple[Command, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class LuksStrategy:
    spec: EncryptionSpec
    crypt_partition_path: str = "/dev/disk/by-partlabel/cryptsystem"

    def commands(self) -> tuple[Command, ...]:
        password = self.spec.password.reveal() if self.spec.password else ""
        return (
            Command(
                argv=(
                    "cryptsetup",
                    "--batch-mode",
                    "luksFormat",
                    "--type",
                    "luks2",
                    self.crypt_partition_path,
                ),
                input=password + "\n",
                sensitive=True,
                description="format LUKS2 container on root partition",
            ),
            Command(
                argv=(
                    "cryptsetup",
                    "open",
                    self.crypt_partition_path,
                    self.spec.mapper_name,
                ),
                input=password + "\n",
                sensitive=True,
                description=f"open LUKS2 container as /dev/mapper/{self.spec.mapper_name}",
            ),
        )


def build_encryption_strategy(spec: EncryptionSpec) -> NoEncryptionStrategy | LuksStrategy:
    if spec.kind is EncryptionKind.NONE:
        return NoEncryptionStrategy()
    return LuksStrategy(spec=spec)
