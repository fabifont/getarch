from pathlib import Path

import pytest

from getarch.domain.disk import Disk
from getarch.errors import EnvironmentError as EnvErr
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.preflight import DiskBusyGuardStep, RuntimePreflightStep


def test_runtime_preflight_runs_ntp_and_keyring() -> None:
    runner = FakeRunner()
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    res = RuntimePreflightStep().execute(ctx)
    assert res.status is StepStatus.SUCCEEDED
    seen = [c.argv for c in runner.recorded]
    assert ("timedatectl", "set-ntp", "true") in seen
    assert ("pacman", "-Sy", "--noconfirm", "archlinux-keyring") in seen
    assert ("pacman-key", "--populate", "archlinux") in seen


class _FakeBlockDevices:
    def __init__(self, mounts: tuple[str, ...]) -> None:
        self._m = mounts

    def list_disks(self) -> tuple[Disk, ...]:
        return ()

    def target_disk_busy(self, path: str) -> tuple[str, ...]:
        del path
        return self._m

    def target_disk_filesystems(self, path: str) -> tuple[tuple[str, str], ...]:
        del path
        return ()


def test_disk_busy_guard_passes_when_clean() -> None:
    step = DiskBusyGuardStep(
        block_devices=_FakeBlockDevices(()),
        target_disk_path="/dev/sda",
    )
    res = step.execute(ExecutionContext(runner=FakeRunner(), mount_root=Path("/mnt")))
    assert res.status is StepStatus.SUCCEEDED


def test_disk_busy_guard_raises_when_busy() -> None:
    step = DiskBusyGuardStep(
        block_devices=_FakeBlockDevices(("/", "/boot")),
        target_disk_path="/dev/sda",
    )
    with pytest.raises(EnvErr, match="mounted partitions"):
        step.execute(ExecutionContext(runner=FakeRunner(), mount_root=Path("/mnt")))
