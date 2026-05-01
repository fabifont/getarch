from dataclasses import dataclass
from pathlib import Path

import pytest

from getarch.execution.context import ExecutionContext
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.pipeline import Pipeline
from getarch.execution.result import StepResult, StepStatus
from getarch.execution.state import PipelineState


@dataclass(frozen=True, slots=True)
class _RecordingStep:
    id: str
    title: str = ""
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        del ctx
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED, commands=())


@dataclass(frozen=True, slots=True)
class _BoomStep:
    id: str
    title: str = ""
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        del ctx
        raise RuntimeError(f"step {self.id} blew up")


def _ctx() -> ExecutionContext:
    return ExecutionContext(runner=FakeRunner(), mount_root=Path("/mnt"))


def test_pipeline_persists_state_after_each_success(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    pipeline = Pipeline(
        steps=(_RecordingStep("a"), _RecordingStep("b"), _RecordingStep("c")),
        state_path=state_path,
    )
    pipeline.run(_ctx())
    state = PipelineState.read(state_path)
    assert state.completed == ["a", "b", "c"]
    assert state.last_error is None


def test_pipeline_records_failure_and_reraises(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    pipeline = Pipeline(
        steps=(_RecordingStep("a"), _BoomStep("b"), _RecordingStep("c")),
        state_path=state_path,
    )
    with pytest.raises(RuntimeError, match="b"):
        pipeline.run(_ctx())
    state = PipelineState.read(state_path)
    assert state.completed == ["a"]
    assert state.last_error is not None
    assert "b" in state.last_error


def test_pipeline_resume_skips_completed_steps(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    PipelineState(completed=["a", "b"]).write(state_path)
    seen: list[str] = []

    @dataclass(frozen=True, slots=True)
    class _Spy:
        id: str
        title: str = ""
        destructive: bool = False

        def execute(self, ctx: ExecutionContext) -> StepResult:
            seen.append(self.id)
            del ctx
            return StepResult(
                step_id=self.id, status=StepStatus.SUCCEEDED, commands=(),
            )

    pipeline = Pipeline(
        steps=(_Spy("a"), _Spy("b"), _Spy("c")),
        state_path=state_path,
        initial_state=PipelineState(completed=["a", "b"]),
    )
    pipeline.run(_ctx())
    assert seen == ["c"]
    state = PipelineState.read(state_path)
    assert state.completed == ["a", "b", "c"]
