"""Pipeline - executes a sequence of steps and aggregates their results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from getarch.execution.context import ExecutionContext
from getarch.execution.result import StepResult


class _Step(Protocol):
    id: str
    title: str
    destructive: bool

    def execute(self, ctx: ExecutionContext) -> StepResult: ...


@dataclass(frozen=True, slots=True)
class Pipeline:
    steps: tuple[_Step, ...]

    def run(self, ctx: ExecutionContext) -> tuple[StepResult, ...]:
        results: list[StepResult] = []
        for step in self.steps:
            results.append(step.execute(ctx))
        return tuple(results)
