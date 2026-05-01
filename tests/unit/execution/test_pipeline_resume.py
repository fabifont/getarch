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


def test_pipeline_never_marks_runtime_guards_completed(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    pipeline = Pipeline(
        steps=(
            _RecordingStep("disk-busy-guard"),
            _RecordingStep("runtime-network-bootstrap"),
            _RecordingStep("runtime-preflight"),
            _RecordingStep("partitioning"),
        ),
        state_path=state_path,
    )
    pipeline.run(_ctx())
    state = PipelineState.read(state_path)
    # Only resumable steps are persisted.
    assert state.completed == ["partitioning"]


def test_pipeline_resume_strips_runtime_guards_from_initial_state(tmp_path: Path) -> None:
    """A stale state file containing runtime guard IDs must NOT cause those
    guards to be skipped on resume."""

    state_path = tmp_path / "state.json"
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

    initial = PipelineState(
        completed=["disk-busy-guard", "runtime-preflight", "partitioning"],
    )
    initial.write(state_path)
    pipeline = Pipeline(
        steps=(
            _Spy("disk-busy-guard"),
            _Spy("runtime-preflight"),
            _Spy("partitioning"),
            _Spy("filesystems"),
        ),
        state_path=state_path,
        initial_state=initial,
    )
    pipeline.run(_ctx())
    # Guards re-run; partitioning skipped (already completed); filesystems runs.
    assert seen == ["disk-busy-guard", "runtime-preflight", "filesystems"]


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
