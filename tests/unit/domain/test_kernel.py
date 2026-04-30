import pytest

from getarch.domain.kernel import KernelKind, KernelSpec, MicrocodeKind


def test_kernel_package_name_property() -> None:
    assert KernelSpec(kind=KernelKind.LINUX).package_name == "linux"
    assert KernelSpec(kind=KernelKind.LTS).package_name == "linux-lts"
    assert KernelSpec(kind=KernelKind.ZEN).package_name == "linux-zen"
    assert KernelSpec(kind=KernelKind.HARDENED).package_name == "linux-hardened"


def test_microcode_package_name() -> None:
    assert MicrocodeKind.INTEL.package_name == "intel-ucode"
    assert MicrocodeKind.AMD.package_name == "amd-ucode"
    assert MicrocodeKind.NONE.package_name is None


def test_initramfs_filename_uses_kernel_kind() -> None:
    spec = KernelSpec(kind=KernelKind.LTS)
    assert spec.image_filename == "vmlinuz-linux-lts"
    assert spec.initramfs_filename == "initramfs-linux-lts.img"


def test_kernelkind_values() -> None:
    assert {k.value for k in KernelKind} == {
        "linux",
        "linux-lts",
        "linux-zen",
        "linux-hardened",
    }


@pytest.mark.parametrize(
    ("vendor", "expected"),
    [
        ("GenuineIntel", MicrocodeKind.INTEL),
        ("AuthenticAMD", MicrocodeKind.AMD),
        ("Hygon Genuine", MicrocodeKind.NONE),
        ("", MicrocodeKind.NONE),
        (None, MicrocodeKind.NONE),
    ],
)
def test_microcode_from_cpu_vendor(vendor: str | None, expected: MicrocodeKind) -> None:
    assert MicrocodeKind.from_cpu_vendor(vendor) is expected
