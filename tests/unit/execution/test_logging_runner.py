import json

from getarch.execution.command import Command
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.execution.logging_runner import LoggingRunner


def test_logging_runner_forwards_and_records() -> None:
    inner = FakeRunner(
        responses={("echo", "ok"): FakeResponse(stdout="ok\n")},
    )
    runner = LoggingRunner(inner=inner)
    result = runner.run(Command(argv=("echo", "ok")))
    assert result.ok
    assert len(runner.lines) == 1
    record = json.loads(runner.lines[0])
    assert record["argv"] == ["echo", "ok"]
    assert record["exit"] == 0


def test_logging_runner_redacts_sensitive_argv_and_input() -> None:
    inner = FakeRunner()
    runner = LoggingRunner(inner=inner)
    runner.run(Command(argv=("chpasswd",), input="root:secret\n", sensitive=True))
    record = json.loads(runner.lines[0])
    assert record["argv"] == ["chpasswd", "<redacted>"]
    assert record["input"] == "***"


def test_logging_runner_render_appends_newlines() -> None:
    inner = FakeRunner()
    runner = LoggingRunner(inner=inner)
    runner.run(Command(argv=("echo", "a")))
    runner.run(Command(argv=("echo", "b")))
    text = runner.render()
    assert text.count("\n") == 2
    assert text.endswith("\n")


def test_logging_runner_records_chroot_path() -> None:
    inner = FakeRunner()
    runner = LoggingRunner(inner=inner)
    runner.run(Command(argv=("echo", "x"), chroot=True), chroot_path="/mnt")
    record = json.loads(runner.lines[0])
    assert record["chroot"] == "/mnt"

    runner.run(Command(argv=("echo", "y")))
    record2 = json.loads(runner.lines[1])
    assert record2["chroot"] is None
