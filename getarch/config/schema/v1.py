"""getarch config schema, version 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)


class DiskConfig(_Frozen):
    path: str = Field(pattern=r"^/dev/[a-zA-Z0-9_+\-/]+$")
    wipe_before: bool = False


class PartitionLayout(_Frozen):
    layout: Literal["efi-root", "efi-swap-root", "efi-home-root", "efi-swap-home-root"] = "efi-root"
    efi_size_mib: int = Field(default=512, ge=128, le=2048)
    swap_size_mib: int | None = Field(default=None, ge=128)
    home_size_mib: int | None = Field(default=None, ge=1024)


class BtrfsSubvolumeConfig(_Frozen):
    name: str = Field(pattern=r"^@[a-zA-Z0-9_-]*$")
    mountpoint: str = Field(pattern=r"^/.*")


_DEFAULT_BTRFS_SUBVOLS: list[BtrfsSubvolumeConfig] = [
    BtrfsSubvolumeConfig(name="@", mountpoint="/"),
    BtrfsSubvolumeConfig(name="@home", mountpoint="/home"),
    BtrfsSubvolumeConfig(name="@snapshots", mountpoint="/.snapshots"),
]


class FilesystemConfig(_Frozen):
    kind: Literal["ext4", "btrfs", "xfs", "f2fs"]
    label: str = "system"
    mount_options: list[str] = Field(default_factory=list)
    subvolumes: list[BtrfsSubvolumeConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _btrfs_defaults(self) -> FilesystemConfig:
        if self.kind == "btrfs" and not self.subvolumes:
            object.__setattr__(self, "subvolumes", list(_DEFAULT_BTRFS_SUBVOLS))
        if self.kind != "btrfs" and self.subvolumes:
            raise ValueError("subvolumes only valid for btrfs")
        return self


class EncryptionConfig(_Frozen):
    kind: Literal["none", "luks2"] = "none"
    password: str | None = None
    mapper_name: str = "system"
    tpm2_unlock: bool = False
    fido2_unlock: bool = False
    header_path: str | None = None

    @model_validator(mode="after")
    def _password_required(self) -> EncryptionConfig:
        if self.kind == "luks2" and not self.password:
            raise ValueError(
                "luks2 requires a password (use prompt or secret-file in future)",
            )
        if self.kind == "none" and (
            self.tpm2_unlock or self.fido2_unlock or self.header_path
        ):
            raise ValueError(
                "tpm2_unlock/fido2_unlock/header_path require encryption.kind='luks2'",
            )
        if self.tpm2_unlock and self.fido2_unlock:
            raise ValueError("set at most one of tpm2_unlock or fido2_unlock")
        if self.header_path:
            # Detached headers require the header file to be reachable at
            # boot via initramfs or external media. Booting the resulting
            # system would need bootloader/initramfs support that getarch
            # does not yet provide. Refuse instead of producing an
            # unbootable system.
            raise ValueError(
                "encryption.header_path is not yet supported: detached LUKS "
                "headers need boot-time access to the header that getarch "
                "cannot guarantee. Track the roadmap for support.",
            )
        return self


class SwapConfig(_Frozen):
    kind: Literal["none", "partition", "swapfile", "zram"] = "none"
    size_mib: int | None = Field(default=None, ge=128)
    zram_size_mib: int | None = Field(default=None, ge=64)

    @model_validator(mode="after")
    def _size_required(self) -> SwapConfig:
        if self.kind == "swapfile" and self.size_mib is None:
            raise ValueError("swap.size_mib required when kind='swapfile'")
        return self


class KernelConfig(_Frozen):
    kind: Literal["linux", "linux-lts", "linux-zen", "linux-hardened"] = "linux"


class MicrocodeConfig(_Frozen):
    kind: Literal["auto", "intel", "amd", "none"] = "auto"


class BootloaderConfig(_Frozen):
    kind: Literal["systemd-boot", "grub", "uki"] = "systemd-boot"
    entry_id: str = "arch"
    timeout_seconds: int = Field(default=5, ge=0, le=120)
    extra_kernel_params: list[str] = Field(default_factory=list)


class InitramfsConfig(_Frozen):
    generator: Literal["mkinitcpio", "dracut"] = "mkinitcpio"
    hooks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _hooks_required_for_mkinitcpio(self) -> InitramfsConfig:
        if self.generator == "mkinitcpio" and not self.hooks:
            raise ValueError("initramfs.hooks must be non-empty for mkinitcpio")
        return self


class LocaleConfig(_Frozen):
    lang: str
    locale: str
    keymap: str
    timezone: str


class SystemdNetworkdProfile(_Frozen):
    name: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    match: dict[str, str] = Field(default_factory=dict)
    network: dict[str, str | list[str]] = Field(default_factory=dict)


class IwdNetworkConfig(_Frozen):
    ssid: str
    psk: str


class NetworkConfig(_Frozen):
    hostname: str
    backend: Literal["networkmanager", "systemd-networkd", "iwd"] = "networkmanager"
    extra_packages: list[str] = Field(default_factory=list)
    systemd_networkd: list[SystemdNetworkdProfile] = Field(default_factory=list)
    iwd_networks: list[IwdNetworkConfig] = Field(default_factory=list)


class ServicesConfig(_Frozen):
    enable: list[str] = Field(default_factory=list)
    timers: list[str] = Field(default_factory=list)


class MirrorsConfig(_Frozen):
    strategy: Literal["keep", "reflector", "static"] = "keep"
    reflector_args: list[str] = Field(default_factory=list)
    static_path: str | None = None

    @model_validator(mode="after")
    def _validate_strategy(self) -> MirrorsConfig:
        if self.strategy == "static" and not self.static_path:
            raise ValueError("static mirror strategy requires static_path")
        return self


class RootAuthConfig(_Frozen):
    kind: Literal["prompt", "plain", "hashed", "secret-file"] = "prompt"
    password: str | None = None
    hashed: str | None = None
    secret_file: str | None = None

    @model_validator(mode="after")
    def _validate_kind(self) -> RootAuthConfig:
        if self.kind == "plain" and not self.password:
            raise ValueError("root.kind=plain requires password")
        if self.kind == "hashed" and not self.hashed:
            raise ValueError("root.kind=hashed requires hashed value")
        if self.kind == "secret-file" and not self.secret_file:
            raise ValueError("root.kind=secret-file requires secret_file path")
        return self


class RegularUserConfig(_Frozen):
    username: str = Field(pattern=r"^[a-z_][a-z0-9_-]{0,30}$")
    password: str | None = None
    hashed_password: str | None = None
    groups: list[str] = Field(default_factory=list)
    shell: str = "/bin/bash"
    sudo: bool = False
    create_home: bool = True


class UsersConfig(_Frozen):
    root: RootAuthConfig
    regular: list[RegularUserConfig] = Field(default_factory=list)


class RepositoryConfig(_Frozen):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    include: str = "/etc/pacman.d/mirrorlist"


class RepositoriesConfig(_Frozen):
    multilib: bool = False
    extra: list[RepositoryConfig] = Field(default_factory=list)


class MountpointConfig(_Frozen):
    """Mount an *existing* partition by partlabel under the new system.

    The partition must live on a disk other than ``disk.path``: the planner
    wipes the target disk's GPT during partitioning, so target-disk
    partitions reachable by partlabel are not safe to attach. Preflight
    refuses configurations that violate this.

    The planner does NOT format the partition. Pre-create the filesystem
    yourself before running getarch.
    """

    partition_label: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    mountpoint: str = Field(pattern=r"^/.+")
    mount_options: list[str] = Field(default_factory=list)


class Config(_Frozen):
    version: Literal[1]
    disk: DiskConfig
    partitioning: PartitionLayout
    filesystem: FilesystemConfig
    encryption: EncryptionConfig
    swap: SwapConfig
    kernel: KernelConfig
    microcode: MicrocodeConfig
    bootloader: BootloaderConfig
    initramfs: InitramfsConfig
    locale: LocaleConfig
    network: NetworkConfig
    packages: list[str] = Field(min_length=1)
    services: ServicesConfig
    mirrors: MirrorsConfig
    users: UsersConfig
    mountpoints: list[MountpointConfig] = Field(default_factory=list)
    repositories: RepositoriesConfig = Field(default_factory=RepositoriesConfig)
    reboot: bool = False

    @field_validator("packages")
    @classmethod
    def _packages_unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("packages list contains duplicates")
        return v
