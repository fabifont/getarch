from pathlib import Path

from getarch import constants


def test_default_mount_root_is_path() -> None:
    assert isinstance(constants.DEFAULT_MOUNT_ROOT, Path)
    assert constants.DEFAULT_MOUNT_ROOT == Path("/mnt")


def test_efivars_path_present() -> None:
    assert constants.EFIVARS_DIR == Path("/sys/firmware/efi/efivars")


def test_default_efi_partition_size_mib() -> None:
    assert constants.DEFAULT_EFI_PART_SIZE_MIB == 512


def test_pacstrap_base_packages_contain_base() -> None:
    assert "base" in constants.BASE_PACKAGES
    assert "linux-firmware" in constants.BASE_PACKAGES
