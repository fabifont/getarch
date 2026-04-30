from pathlib import Path

from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner


def test_context_carries_runner_and_mount_root() -> None:
    runner = FakeRunner()
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"), assume_yes=True)
    assert ctx.runner is runner
    assert ctx.mount_root == Path("/mnt")
    assert ctx.assume_yes is True


def test_context_default_assume_yes_false() -> None:
    ctx = ExecutionContext(runner=FakeRunner(), mount_root=Path("/mnt"))
    assert ctx.assume_yes is False
