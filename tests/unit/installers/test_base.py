from pathlib import Path

from getarch.domain.plan import PlannedStep, StepPhase
from getarch.execution.command import Command
from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeResponse, FakeRunner
from getarch.execution.result import StepStatus
from getarch.installers.base import PlannedStepExecutor


def _step(commands: tuple[Command, ...], *, destructive: bool = False) -> PlannedStep:
    return PlannedStep(
        id="x",
        title="X",
        phase=StepPhase.PARTITIONING,
        commands=commands,
        destructive=destructive,
        description="d",
    )


def test_executor_runs_commands_in_order() -> None:
    runner = FakeRunner()
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    step = _step((Command(argv=("a",)), Command(argv=("b",))))
    res = PlannedStepExecutor(planned=step).execute(ctx)
    assert res.status is StepStatus.SUCCEEDED
    assert [c.argv for c in runner.recorded] == [("a",), ("b",)]


def test_executor_returns_failed_status_on_command_error() -> None:
    runner = FakeRunner(
        responses={("false",): FakeResponse(returncode=1, stderr="boom")},
    )
    ctx = ExecutionContext(runner=runner, mount_root=Path("/mnt"))
    step = _step((Command(argv=("false",), check=False),))
    res = PlannedStepExecutor(planned=step).execute(ctx)
    assert res.status is StepStatus.FAILED
