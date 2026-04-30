from getarch.execution.command import Command
from getarch.execution.result import CommandResult, StepResult, StepStatus


def test_command_result_success() -> None:
    cmd = Command(argv=("true",))
    res = CommandResult(command=cmd, returncode=0, stdout="", stderr="")
    assert res.ok


def test_command_result_failure() -> None:
    cmd = Command(argv=("false",))
    res = CommandResult(command=cmd, returncode=1, stdout="", stderr="boom")
    assert not res.ok


def test_step_result_aggregates_command_results() -> None:
    cmd = Command(argv=("true",))
    sr = StepResult(
        step_id="preflight",
        status=StepStatus.SUCCEEDED,
        commands=(CommandResult(command=cmd, returncode=0, stdout="", stderr=""),),
    )
    assert sr.status is StepStatus.SUCCEEDED
    assert len(sr.commands) == 1
