from pathlib import Path

import pytest

from getarch.errors import CommandFailedError
from getarch.execution.command import Command
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.result import StepResult, StepStatus


class _GoodStep:
    id: str = "good"
    title: str = "Good step"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        ctx.runner.run(Command(argv=("true",)))
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED)


class _BadStep:
    id: str = "bad"
    title: str = "Bad step"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        ctx.runner.run(Command(argv=("false",)))
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED)


def test_pipeline_runs_steps_in_order() -> None:
    runner = FakeRunner()
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    results = Pipeline(steps=(_GoodStep(),)).run(ctx)
    assert [r.step_id for r in results] == ["good"]
    assert results[0].status is StepStatus.SUCCEEDED


def test_pipeline_propagates_command_failure() -> None:
    runner = FakeRunner(responses={("false",): FakeResponse(returncode=1)})
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    with pytest.raises(CommandFailedError):
        Pipeline(steps=(_BadStep(),)).run(ctx)
