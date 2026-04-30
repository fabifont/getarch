from pathlib import Path

from getarch.system.iso import OsReleaseIso


def test_arch_iso_recognised(tmp_path: Path) -> None:
    f = tmp_path / "os-release"
    f.write_text(
        'NAME="Arch Linux"\nID=arch\nIMAGE_ID=archlinux\nIMAGE_VERSION=2026.04\n'
    )
    assert OsReleaseIso(path=f).is_arch_iso() is True


def test_arch_installed_no_image_id(tmp_path: Path) -> None:
    f = tmp_path / "os-release"
    f.write_text('NAME="Arch Linux"\nID=arch\n')
    assert OsReleaseIso(path=f).is_arch_iso() is False


def test_non_arch_distro(tmp_path: Path) -> None:
    f = tmp_path / "os-release"
    f.write_text('NAME="Ubuntu"\nID=ubuntu\nIMAGE_ID=ubuntu\n')
    assert OsReleaseIso(path=f).is_arch_iso() is False


def test_missing_file(tmp_path: Path) -> None:
    assert OsReleaseIso(path=tmp_path / "missing").is_arch_iso() is False


def test_unquoted_values(tmp_path: Path) -> None:
    f = tmp_path / "os-release"
    f.write_text("ID=arch\nIMAGE_ID=archlinux\n")
    assert OsReleaseIso(path=f).is_arch_iso() is True
