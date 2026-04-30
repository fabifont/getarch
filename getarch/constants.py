"""Constants and well-known paths used across getarch.

Nothing in this module reads the environment or the filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

DEFAULT_MOUNT_ROOT: Final = Path("/mnt")
EFIVARS_DIR: Final = Path("/sys/firmware/efi/efivars")
DEFAULT_EFI_PART_SIZE_MIB: Final = 512
DEFAULT_BTRFS_MOUNT_OPTIONS: Final = (
    "defaults",
    "x-mount.mkdir",
    "noatime",
    "nodiratime",
    "compress=zstd",
    "space_cache=v2",
    "ssd",
)
DEFAULT_BTRFS_SUBVOLUMES: Final = (
    ("@", Path("/")),
    ("@home", Path("/home")),
    ("@snapshots", Path("/.snapshots")),
)
BASE_PACKAGES: Final = ("base", "base-devel", "linux-firmware", "sudo")
INTERNET_REACHABILITY_HOST: Final = "archlinux.org"
INTERNET_REACHABILITY_TIMEOUT_SECONDS: Final = 3.0
PACMAN_KEYRING_PATH: Final = Path("/etc/pacman.d/gnupg/pubring.gpg")
