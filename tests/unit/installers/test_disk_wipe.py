from pathlib import Path

import pytest

from getarch.errors import CommandFailedError
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.preflight import DiskWipeStep


def _ctx(runner: FakeRunner) -> ExecutionContext:
    return ExecutionContext(runner=runner, mount_root=Path("/mnt"))


def test_wipe_runs_wipefs_and_blkdiscard() -> None:
    runner = FakeRunner()
    res = DiskWipeStep(target_disk_path="/dev/sda").execute(_ctx(runner))
    assert res.status is StepStatus.SUCCEEDED
    argvs = [c.argv for c in runner.recorded]
    assert ("wipefs", "-a", "-f", "/dev/sda") in argvs
    assert ("blkdiscard", "-f", "/dev/sda") in argvs


def test_blkdiscard_failure_does_not_fail_step() -> None:
    runner = FakeRunner(
        responses={("blkdiscard", "-f", "/dev/sda"): FakeResponse(returncode=1)},
    )
    res = DiskWipeStep(target_disk_path="/dev/sda").execute(_ctx(runner))
    # wipefs succeeded, blkdiscard returned non-zero (HDD with no discard
    # support); the step is still a success.
    assert res.status is StepStatus.SUCCEEDED


def test_wipefs_failure_fails_step() -> None:
    runner = FakeRunner(
        responses={
            ("wipefs", "-a", "-f", "/dev/sda"): FakeResponse(
                returncode=1, stderr="boom",
            ),
        },
    )
    # wipefs has check=True so it raises CommandFailedError before we even
    # see the StepResult; that's the desired behaviour.
    with pytest.raises(CommandFailedError):
        DiskWipeStep(target_disk_path="/dev/sda").execute(_ctx(runner))
