"""LUKS2 encryption strategies (plain, TPM2 enroll, FIDO2 enroll).

Detached header support is layered into :class:`LuksStrategy` so every
``cryptsetup`` invocation gets ``--header=<header_path>`` when configured.
"""

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
        header_args: tuple[str, ...] = (
            ("--header", self.spec.header_path) if self.spec.header_path else ()
        )
        cmds: list[Command] = [
            Command(
                argv=(
                    "cryptsetup",
                    "--batch-mode",
                    "luksFormat",
                    "--type",
                    "luks2",
                    *header_args,
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
                    *header_args,
                    self.crypt_partition_path,
                    self.spec.mapper_name,
                ),
                input=password + "\n",
                sensitive=True,
                description=f"open LUKS2 container as /dev/mapper/{self.spec.mapper_name}",
            ),
        ]
        if self.spec.tpm2_unlock:
            cmds.append(
                Command(
                    argv=(
                        "systemd-cryptenroll",
                        "--tpm2-device=auto",
                        self.crypt_partition_path,
                    ),
                    input=password + "\n",
                    sensitive=True,
                    description="enroll TPM2 device for unattended unlock",
                ),
            )
        if self.spec.fido2_unlock:
            cmds.append(
                Command(
                    argv=(
                        "systemd-cryptenroll",
                        "--fido2-device=auto",
                        self.crypt_partition_path,
                    ),
                    input=password + "\n",
                    sensitive=True,
                    description="enroll FIDO2 device for unattended unlock",
                ),
            )
        return tuple(cmds)


def build_encryption_strategy(spec: EncryptionSpec) -> NoEncryptionStrategy | LuksStrategy:
    if spec.kind is EncryptionKind.NONE:
        return NoEncryptionStrategy()
    return LuksStrategy(spec=spec)
