from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.real_runner import RealRunner


def _patch_run(
    mocker: MockerFixture, *, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> MagicMock:
    mock_run = MagicMock()
    mock_run.return_value.returncode = returncode
    mock_run.return_value.stdout = stdout
    mock_run.return_value.stderr = stderr
    mocker.patch("getarch.execution.real_runner.subprocess.run", mock_run)
    return mock_run


def test_real_runner_calls_subprocess_with_argv_list(mocker: MockerFixture) -> None:
    mock_run = _patch_run(mocker, stdout="hi\n")
    RealRunner().run(Command(argv=("echo", "hi")))
    args, kwargs = mock_run.call_args
    assert args[0] == ["echo", "hi"]
    assert kwargs["shell"] is False
    assert kwargs["check"] is False
    assert kwargs["text"] is True


def test_real_runner_raises_on_nonzero(mocker: MockerFixture) -> None:
    _patch_run(mocker, returncode=2, stderr="fail")
    with pytest.raises(CommandFailedError):
        RealRunner().run(Command(argv=("false",)))


def test_real_runner_passes_chroot(mocker: MockerFixture) -> None:
    mock_run = _patch_run(mocker)
    RealRunner().run(
        Command(argv=("pacman", "-Sy"), chroot=True),
        chroot_path="/mnt",
    )
    args, _ = mock_run.call_args
    assert args[0] == ["arch-chroot", "/mnt", "pacman", "-Sy"]


def test_real_runner_redacts_in_logs(
    mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_run(mocker)
    with caplog.at_level("DEBUG", logger="getarch"):
        RealRunner().run(
            Command(argv=("passwd", "root"), input="hunter2", sensitive=True),
        )
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "hunter2" not in joined
