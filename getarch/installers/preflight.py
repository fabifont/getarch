"""Runtime-only preflight performed before the planned pipeline runs."""

from __future__ import annotations

from getarch.execution.command import Command
from getarch.execution.context import ExecutionContext
from getarch.execution.result import CommandResult, StepResult, StepStatus


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
        status = (
            StepStatus.SUCCEEDED if all(r.ok for r in results) else StepStatus.FAILED
        )
        return StepResult(step_id=self.id, status=status, commands=tuple(results))
