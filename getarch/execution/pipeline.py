"""Pipeline - executes a sequence of steps and aggregates their results.

Optionally persists per-step success state so a failed install can be
resumed by skipping the already-completed steps. State is written under
``<mount>/var/log/getarch.state.json`` after every successful step and
on failure (with ``last_error`` populated).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from getarch.execution.context import ExecutionContext
from getarch.execution.result import StepResult
from getarch.execution.state import PipelineState


class _Step(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def destructive(self) -> bool: ...
    def execute(self, ctx: ExecutionContext) -> StepResult: ...


# Steps that always re-run on resume — guards and runtime bring-up that
# must reflect *current* state, not yesterday's state. Adding an ID here
# both prevents skipping during resume and prevents persisting it as
# completed.
_NON_RESUMABLE_STEP_IDS: frozenset[str] = frozenset(
    {
        "disk-busy-guard",
        "runtime-network-bootstrap",
        "runtime-preflight",
    },
)


@dataclass(frozen=True, slots=True)
class Pipeline:
    steps: tuple[_Step, ...]
    state_path: Path | None = None
    initial_state: PipelineState = field(default_factory=PipelineState)

    def run(self, ctx: ExecutionContext) -> tuple[StepResult, ...]:
        state = PipelineState(
            completed=[
                sid
                for sid in self.initial_state.completed
                if sid not in _NON_RESUMABLE_STEP_IDS
            ],
            last_error=self.initial_state.last_error,
            plan_fingerprint=self.initial_state.plan_fingerprint,
            plan_blob=self.initial_state.plan_blob,
        )
        results: list[StepResult] = []
        for step in self.steps:
            if step.id in state.completed:
                continue
            try:
                result = step.execute(ctx)
            except BaseException as exc:
                state.last_error = f"{type(exc).__name__}: {exc}"
                self._persist(state)
                raise
            results.append(result)
            if step.id not in _NON_RESUMABLE_STEP_IDS:
                state.completed.append(step.id)
            state.last_error = None
            self._persist(state)
        return tuple(results)

    def _persist(self, state: PipelineState) -> None:
        if self.state_path is None:
            return
        try:
            state.write(self.state_path)
        except OSError:
            # State persistence is best-effort: the target mount may not
            # exist yet (we run before the partitioning step succeeds) or
            # may be read-only. The original step result/exception still
            # propagates to the caller.
            return
