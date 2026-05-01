"""getarch config schema, version 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=False)


class DiskConfig(_Frozen):
    path: str = Field(pattern=r"^/dev/[a-zA-Z0-9_+\-/]+$")
    wipe_before: bool = False


class LvmVolume(_Frozen):
    """One logical volume inside the LVM-on-LUKS volume group.

    ``size_mib`` is the explicit size in MiB; pass ``None`` exactly once
    in :class:`LvmConfig.volumes` to mean "use the rest of the VG"
    (i.e. ``lvcreate -l 100%FREE``).
    """

    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    size_mib: int | None = Field(default=None, ge=64)
    mountpoint: str = Field(pattern=r"^/.*")
    filesystem: Literal["ext4", "btrfs", "xfs", "f2fs"] = "ext4"


class LvmConfig(_Frozen):
    """LVM-on-LUKS volume group sitting on top of the root LUKS mapper.

    Requires ``encryption.kind='luks2'`` (semantic check). Mutually
    exclusive with the ``home`` partition role in
    :attr:`PartitionLayout.layout` — declare a ``home`` LV instead.
    """

    vg_name: str = Field(default="system", pattern=r"^[a-zA-Z0-9_-]+$")
    volumes: list[LvmVolume] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_volumes(self) -> LvmConfig:
        names = [v.name for v in self.volumes]
        if len(names) != len(set(names)):
            raise ValueError("lvm.volumes have duplicate names")
        mountpoints = [v.mountpoint for v in self.volumes]
        if "/" not in mountpoints:
            raise ValueError("lvm.volumes must include one with mountpoint='/'")
        if len(set(mountpoints)) != len(mountpoints):
            raise ValueError("lvm.volumes have duplicate mountpoints")
        unsized = [v for v in self.volumes if v.size_mib is None]
        if len(unsized) > 1:
            raise ValueError(
                "lvm.volumes may have at most one volume with no size_mib "
                "(it consumes the rest of the VG)",
            )
        return self


class CustomPartition(_Frozen):
    """Single GPT partition in :attr:`PartitionLayout.custom`.

    ``label`` becomes the GPT partition name (also the
    ``/dev/disk/by-partlabel/<label>`` symlink). ``typecode`` is the
    sgdisk short type GUID. ``role`` tells the planner what semantic
    slot this partition fills:

    * ``efi`` — ESP, mounted at ``/boot``
    * ``root`` — root filesystem (LUKS container if encryption is on)
    * ``home`` — separate home partition
    * ``swap`` — swap partition
    * ``luksheader`` — detached LUKS header carrier
    * ``extra`` — user-mounted via :attr:`Config.mountpoints`
    """

    label: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    size_mib: int | None = Field(default=None, ge=1)
    typecode: str = Field(default="8300", pattern=r"^[0-9a-fA-F]{4}$")
    role: Literal["root", "home", "efi", "swap", "luksheader", "extra"] = "extra"


class PartitionLayout(_Frozen):
    layout: Literal[
        "efi-root",
        "efi-swap-root",
        "efi-home-root",
        "efi-swap-home-root",
        "efi-luksheader-root",
        "efi-swap-luksheader-root",
    ] = "efi-root"
    efi_size_mib: int = Field(default=512, ge=128, le=2048)
    swap_size_mib: int | None = Field(default=None, ge=128)
    home_size_mib: int | None = Field(default=None, ge=1024)
    root_size_mib: int | None = Field(default=None, ge=4096)
    lvm: LvmConfig | None = None
    custom: list[CustomPartition] | None = None

    @model_validator(mode="after")
    def _validate_lvm(self) -> PartitionLayout:
        if self.lvm is not None and "home" in self.layout:
            raise ValueError(
                "partitioning.lvm conflicts with a 'home' partition role; "
                "declare a home LV in lvm.volumes instead",
            )
        return self

    @model_validator(mode="after")
    def _validate_custom(self) -> PartitionLayout:
        if self.custom is None:
            return self
        if self.lvm is not None:
            raise ValueError(
                "partitioning.custom is mutually exclusive with partitioning.lvm",
            )
        labels = [p.label for p in self.custom]
        if len(labels) != len(set(labels)):
            raise ValueError("partitioning.custom partitions have duplicate labels")
        roles = [p.role for p in self.custom if p.role != "extra"]
        for required in ("efi", "root"):
            if required not in roles:
                raise ValueError(
                    f"partitioning.custom must include exactly one role={required!r}",
                )
        for role in roles:
            if roles.count(role) > 1:
                raise ValueError(
                    f"partitioning.custom has {roles.count(role)} partitions with "
                    f"role={role!r}; only 'extra' may repeat",
                )
        unsized = [p for p in self.custom if p.size_mib is None]
        if len(unsized) > 1:
            raise ValueError(
                "partitioning.custom may have at most one partition with no "
                "size_mib (it consumes the rest of the disk)",
            )
        return self


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
    snapper: bool = False

    @model_validator(mode="after")
    def _btrfs_defaults(self) -> FilesystemConfig:
        if self.kind == "btrfs" and not self.subvolumes:
            object.__setattr__(self, "subvolumes", list(_DEFAULT_BTRFS_SUBVOLS))
        if self.kind != "btrfs" and self.subvolumes:
            raise ValueError("subvolumes only valid for btrfs")
        if self.snapper and self.kind != "btrfs":
            raise ValueError("snapper requires filesystem.kind='btrfs'")
        return self


class EncryptionConfig(_Frozen):
    kind: Literal["none", "luks2"] = "none"
    password: str | None = None
    mapper_name: str = "system"
    tpm2_unlock: bool = False
    fido2_unlock: bool = False
    header_path: str | None = None
    home_kind: Literal["none", "shared-key", "separate-key"] = "none"
    home_password: str | None = None
    home_keyfile: bool = False

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
        if self.home_kind != "none" and self.kind != "luks2":
            raise ValueError(
                "encryption.home_kind requires encryption.kind='luks2'",
            )
        if self.home_kind == "separate-key" and not self.home_password:
            raise ValueError(
                "encryption.home_kind='separate-key' requires encryption.home_password",
            )
        if self.home_keyfile and self.home_kind == "none":
            raise ValueError(
                "encryption.home_keyfile requires encryption.home_kind != 'none'",
            )
        return self


class SwapConfig(_Frozen):
    kind: Literal["none", "partition", "swapfile", "zram"] = "none"
    size_mib: int | None = Field(default=None, ge=128)
    zram_size_mib: int | None = Field(default=None, ge=64)
    encrypt: bool = False

    @model_validator(mode="after")
    def _size_required(self) -> SwapConfig:
        if self.kind == "swapfile" and self.size_mib is None:
            raise ValueError("swap.size_mib required when kind='swapfile'")
        if self.encrypt and self.kind != "partition":
            raise ValueError(
                "swap.encrypt requires swap.kind='partition' (random-key "
                "dm-crypt only makes sense for a real swap partition)",
            )
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
    locale: list[str] = Field(min_length=1)
    keymap: str
    timezone: str

    @field_validator("locale", mode="before")
    @classmethod
    def _wrap_single_locale(cls, value: object) -> object:
        # Back-compat: a JSON string is auto-promoted to a single-element list.
        if isinstance(value, str):
            return [value]
        return value


class SystemdNetworkdProfile(_Frozen):
    name: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    match: dict[str, str] = Field(default_factory=dict)
    network: dict[str, str | list[str]] = Field(default_factory=dict)


class SystemdNetworkdNetdev(_Frozen):
    """A virtual link rendered as ``/etc/systemd/network/<name>.netdev``.

    The ``properties`` mapping is split between the ``[NetDev]`` section
    (``Name`` + ``Kind`` are emitted automatically) and the kind-specific
    section (``[VLAN]``, ``[Bridge]``, ``[Bond]``). Any key whose name
    matches a kind-specific field (``Id``, ``Protocol`` for VLAN; the
    bridge/bond manuals enumerate the rest) lands in the kind section;
    everything else falls back to ``[NetDev]``.
    """

    name: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    kind: Literal["vlan", "bridge", "bond"]
    properties: dict[str, str] = Field(default_factory=dict)


class SystemdNetworkdLink(_Frozen):
    """A ``/etc/systemd/network/<name>.link`` file.

    Rendered as two sections: ``[Match]`` (``match`` mapping) and
    ``[Link]`` (``link`` mapping).
    """

    name: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    match: dict[str, str] = Field(default_factory=dict)
    link: dict[str, str | list[str]] = Field(default_factory=dict)


class IwdNetworkConfig(_Frozen):
    ssid: str
    psk: str


class WifiBootstrap(_Frozen):
    kind: Literal["iwctl"] = "iwctl"
    device: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    ssid: str
    psk: str


class WiredBootstrap(_Frozen):
    kind: Literal["dhcp"] = "dhcp"
    device: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")


class WifiEnterpriseBootstrap(_Frozen):
    kind: Literal["iwctl-eap"] = "iwctl-eap"
    device: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    ssid: str
    username: str
    password: str | None = None
    cert_path: str | None = None
    private_key_path: str | None = None
    ca_cert_path: str | None = None
    eap_method: Literal["PEAP", "TLS", "TTLS"] = "PEAP"

    @model_validator(mode="after")
    def _credentials_present(self) -> WifiEnterpriseBootstrap:
        has_password = bool(self.password)
        has_cert = bool(self.cert_path) and bool(self.private_key_path)
        if not (has_password or has_cert):
            raise ValueError(
                "iwctl-eap bootstrap requires either a password (PEAP/TTLS) "
                "or a cert_path+private_key_path pair (TLS)",
            )
        return self


class WireguardBootstrap(_Frozen):
    kind: Literal["wireguard"] = "wireguard"
    config_path: str
    device: str = "wg0"


class NetworkConfig(_Frozen):
    hostname: str
    backend: Literal["networkmanager", "systemd-networkd", "iwd"] = "networkmanager"
    extra_packages: list[str] = Field(default_factory=list)
    systemd_networkd: list[SystemdNetworkdProfile] = Field(default_factory=list)
    systemd_networkd_netdevs: list[SystemdNetworkdNetdev] = Field(default_factory=list)
    systemd_networkd_links: list[SystemdNetworkdLink] = Field(default_factory=list)
    iwd_networks: list[IwdNetworkConfig] = Field(default_factory=list)
    bootstrap: (
        WifiBootstrap
        | WiredBootstrap
        | WifiEnterpriseBootstrap
        | WireguardBootstrap
        | None
    ) = Field(default=None)
    firewall_nftables_rules: list[str] = Field(default_factory=list)


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
    firmware: Literal["uefi", "bios", "container"] = "uefi"
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
