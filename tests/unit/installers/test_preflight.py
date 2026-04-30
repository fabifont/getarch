from pathlib import Path

from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.preflight import RuntimePreflightStep


def test_runtime_preflight_runs_ntp_and_keyring() -> None:
    runner = FakeRunner()
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    res = RuntimePreflightStep().execute(ctx)
    assert res.status is StepStatus.SUCCEEDED
    seen = [c.argv for c in runner.recorded]
    assert ("timedatectl", "set-ntp", "true") in seen
    assert ("pacman", "-Sy", "--noconfirm", "archlinux-keyring") in seen
    assert ("pacman-key", "--populate", "archlinux") in seen
