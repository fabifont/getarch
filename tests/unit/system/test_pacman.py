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
