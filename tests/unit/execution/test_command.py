import pytest

from getarch.execution.command import Command


def test_command_is_frozen() -> None:
    cmd = Command(argv=("ls", "-la"))
    with pytest.raises(AttributeError):
        cmd.argv = ("rm",)  # type: ignore[misc]


def test_argv_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="argv"):
        Command(argv=())


def test_render_uses_chroot_prefix_when_requested() -> None:
    cmd = Command(argv=("pacman", "-Sy"), chroot=True)
    assert cmd.render(chroot_path="/mnt") == ("arch-chroot", "/mnt", "pacman", "-Sy")


def test_render_without_chroot() -> None:
    cmd = Command(argv=("ls", "/"))
    assert cmd.render(chroot_path="/mnt") == ("ls", "/")


def test_describe_redacts_when_sensitive() -> None:
    cmd = Command(argv=("passwd",), input="hunter2", sensitive=True)
    described = cmd.describe()
    assert "hunter2" not in described
    assert "passwd" in described


def test_describe_includes_argv_when_not_sensitive() -> None:
    cmd = Command(argv=("ls", "/etc"))
    assert "ls" in cmd.describe()
    assert "/etc" in cmd.describe()
