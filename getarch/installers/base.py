"""Bridge between PlannedStep (data) and the pipeline (executor)."""

from __future__ import annotations

from dataclasses import dataclass

from getarch.domain.plan import PlannedStep
from getarch.execution.context import ExecutionContext
from getarch.execution.result import CommandResult, StepResult, StepStatus


@dataclass(frozen=True, slots=True)
class PlannedStepExecutor:
    planned: PlannedStep

    @property
    def id(self) -> str:
        return self.planned.id

    @property
    def title(self) -> str:
        return self.planned.title

    @property
    def destructive(self) -> bool:
        return self.planned.destructive

    def execute(self, ctx: ExecutionContext) -> StepResult:
        results: list[CommandResult] = []
        for cmd in self.planned.commands:
            results.append(ctx.runner.run(cmd, chroot_path=str(ctx.mount_root)))
        status = (
            StepStatus.SUCCEEDED
            if all(r.ok for r in results)
            else StepStatus.FAILED
        )
        return StepResult(
            step_id=self.planned.id,
            status=status,
            commands=tuple(results),
        )
