from pathlib import Path

from getarch.system.firmware import EfivarsFirmware


def test_uefi_present(tmp_path: Path) -> None:
    efivars = tmp_path / "efivars"
    efivars.mkdir()
    (efivars / "marker").write_text("x")
    fw = EfivarsFirmware(efivars_dir=efivars)
    assert fw.is_uefi() is True


def test_uefi_absent(tmp_path: Path) -> None:
    fw = EfivarsFirmware(efivars_dir=tmp_path / "missing")
    assert fw.is_uefi() is False
