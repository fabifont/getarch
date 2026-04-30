from getarch.execution.command import Command
from getarch.execution.dry_runner import DryRunner


def test_dry_runner_records_and_returns_zero() -> None:
    runner = DryRunner()
    res = runner.run(Command(argv=("mkfs.ext4", "/dev/sda2")))
    assert res.returncode == 0
    assert res.stdout == ""
    assert runner.recorded[-1].argv == ("mkfs.ext4", "/dev/sda2")


def test_dry_runner_does_not_raise_on_check_true() -> None:
    runner = DryRunner()
    runner.run(Command(argv=("false",), check=True))


def test_dry_runner_chroot_render_recorded() -> None:
    runner = DryRunner()
    runner.run(Command(argv=("pacman", "-Sy"), chroot=True), chroot_path="/mnt")
    assert runner.rendered[-1] == ("arch-chroot", "/mnt", "pacman", "-Sy")
