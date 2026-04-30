from getarch.domain.bootloader import BootloaderKind, BootloaderSpec


def test_systemd_boot_default_entry() -> None:
    spec = BootloaderSpec(kind=BootloaderKind.SYSTEMD_BOOT)
    assert spec.entry_id == "arch"
    assert spec.timeout_seconds == 5


def test_extra_kernel_params_tuple() -> None:
    spec = BootloaderSpec(
        kind=BootloaderKind.SYSTEMD_BOOT,
        extra_kernel_params=("quiet", "splash"),
    )
    assert spec.extra_kernel_params == ("quiet", "splash")
