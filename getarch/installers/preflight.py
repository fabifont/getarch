"""Runtime-only preflight steps that run inside the install pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from getarch.errors import EnvironmentError as _EnvErr
from getarch.execution.command import Command
from getarch.execution.context import ExecutionContext
from getarch.execution.result import CommandResult, StepResult, StepStatus
from getarch.system.discovery import BlockDeviceProvider


class RuntimePreflightStep:
    id: str = "runtime-preflight"
    title: str = "Runtime preflight"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        commands = (
            Command(
                argv=("timedatectl", "set-ntp", "true"),
                description="enable NTP",
            ),
            Command(
                argv=("pacman", "-Sy", "--noconfirm", "archlinux-keyring"),
                description="refresh archlinux-keyring",
            ),
            Command(argv=("pacman-key", "--init"), description="init pacman keyring"),
            Command(
                argv=("pacman-key", "--populate", "archlinux"),
                description="populate pacman keyring with arch master keys",
            ),
        )
        results: list[CommandResult] = [
            ctx.runner.run(c, chroot_path=str(ctx.mount_root)) for c in commands
        ]
        status = StepStatus.SUCCEEDED if all(r.ok for r in results) else StepStatus.FAILED
        return StepResult(step_id=self.id, status=status, commands=tuple(results))


@dataclass(frozen=True, slots=True)
class DiskBusyGuardStep:
    """Refresh-mount-state guard inserted before any destructive plan step.

    Holds its own :class:`BlockDeviceProvider` so the check uses the real
    system view independently of ``ExecutionContext.runner`` (which may be a
    :class:`DryRunner`). Cannot be bypassed by ``--skip-environment-preflight``
    or ``--yes``/``--force`` — refusing is the whole job.
    """

    block_devices: BlockDeviceProvider
    target_disk_path: str
    id: str = "disk-busy-guard"
    title: str = "Disk-busy guard"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        del ctx
        mounts = self.block_devices.target_disk_busy(self.target_disk_path)
        if mounts:
            raise _EnvErr(
                f"target disk {self.target_disk_path} has mounted partitions: "
                f"{', '.join(mounts)}. Refusing to proceed.",
            )
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED, commands=())
