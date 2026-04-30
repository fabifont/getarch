from pathlib import Path

import pytest

from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.system.pacman import Pacman


def test_package_exists_returns_true_when_pacman_returns_zero() -> None:
    runner = FakeRunner(
        responses={
            ("pacman", "-Si", "linux"): FakeResponse(returncode=0, stdout="..."),
        },
    )
    assert Pacman(runner=runner).package_exists("linux")


def test_package_exists_returns_false_on_nonzero() -> None:
    runner = FakeRunner(
        responses={("pacman", "-Si", "doesnotexist"): FakeResponse(returncode=1)},
    )
    assert not Pacman(runner=runner).package_exists("doesnotexist")


def test_package_name_validation_rejects_shell_metachars() -> None:
    runner = FakeRunner()
    pac = Pacman(runner=runner)
    with pytest.raises(ValueError, match="invalid package name"):
        pac.package_exists("foo; rm -rf /")


def test_keyring_initialized_true(tmp_path: Path) -> None:
    keyring = tmp_path / "pubring.gpg"
    keyring.write_bytes(b"\x99\x01\x02")
    pac = Pacman(runner=FakeRunner(), keyring_path=keyring)
    assert pac.keyring_initialized() is True


def test_keyring_initialized_false_missing(tmp_path: Path) -> None:
    pac = Pacman(runner=FakeRunner(), keyring_path=tmp_path / "missing")
    assert pac.keyring_initialized() is False


def test_keyring_initialized_false_empty(tmp_path: Path) -> None:
    keyring = tmp_path / "pubring.gpg"
    keyring.write_bytes(b"")
    pac = Pacman(runner=FakeRunner(), keyring_path=keyring)
    assert pac.keyring_initialized() is False
