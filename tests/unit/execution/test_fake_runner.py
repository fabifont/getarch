import pytest

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.fake_runner import FakeResponse, FakeRunner


def test_records_commands() -> None:
    runner = FakeRunner()
    runner.run(Command(argv=("ls", "/")))
    runner.run(Command(argv=("uname", "-r")))
    assert [c.argv for c in runner.recorded] == [("ls", "/"), ("uname", "-r")]


def test_returns_canned_response_by_argv_prefix() -> None:
    runner = FakeRunner(
        responses={
            ("uname", "-r"): FakeResponse(stdout="6.10.0-arch1-1\n"),
        }
    )
    res = runner.run(Command(argv=("uname", "-r")))
    assert res.stdout == "6.10.0-arch1-1\n"
    assert res.ok


def test_raises_command_failed_when_check_and_nonzero() -> None:
    runner = FakeRunner(
        responses={("false",): FakeResponse(returncode=1, stderr="bad")},
    )
    with pytest.raises(CommandFailedError):
        runner.run(Command(argv=("false",), check=True))


def test_check_false_does_not_raise() -> None:
    runner = FakeRunner(responses={("false",): FakeResponse(returncode=1)})
    res = runner.run(Command(argv=("false",), check=False))
    assert res.returncode == 1


def test_chroot_render_recorded() -> None:
    runner = FakeRunner()
    runner.run(Command(argv=("pacman", "-Sy"), chroot=True), chroot_path="/mnt")
    rendered = runner.rendered[-1]
    assert rendered[:2] == ("arch-chroot", "/mnt")
