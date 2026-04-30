import pytest

from getarch.domain.plan import InstallPlan, PlannedStep, StepPhase
from getarch.execution.command import Command


def test_planned_step_must_have_id_and_title() -> None:
    PlannedStep(
        id="preflight",
        title="Preflight",
        phase=StepPhase.PREFLIGHT,
        commands=(),
        destructive=False,
        description="x",
    )
    with pytest.raises(ValueError):
        PlannedStep(
            id="",
            title="",
            phase=StepPhase.PREFLIGHT,
            commands=(),
            destructive=False,
            description="x",
        )


def test_install_plan_step_ids_unique() -> None:
    s1 = PlannedStep(
        id="a",
        title="A",
        phase=StepPhase.PREFLIGHT,
        commands=(),
        destructive=False,
        description="d",
    )
    with pytest.raises(ValueError, match="duplicate"):
        InstallPlan(version="1", steps=(s1, s1))


def test_install_plan_destructive_property() -> None:
    s = PlannedStep(
        id="part",
        title="Partition",
        phase=StepPhase.PARTITIONING,
        commands=(Command(argv=("sgdisk",)),),
        destructive=True,
        description="d",
    )
    assert InstallPlan(version="1", steps=(s,)).has_destructive_steps
