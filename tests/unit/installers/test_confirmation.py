from pathlib import Path

import pytest

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.domain.plan import InstallPlan, PlannedStep, StepPhase
from getarch.errors import EnvironmentError as EnvErr
from getarch.installers.confirmation import require_destructive_confirmation
from getarch.planning.planner import Planner


def _plan() -> InstallPlan:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    return Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),
        mount_root=Path("/mnt"),
    )


def test_assume_yes_skips_prompt() -> None:
    require_destructive_confirmation(_plan(), assume_yes=True, force=False, prompt=lambda _: False)


def test_force_skips_prompt() -> None:
    require_destructive_confirmation(_plan(), assume_yes=False, force=True, prompt=lambda _: False)


def test_no_destructive_steps_no_prompt() -> None:
    plan = InstallPlan(
        version="1",
        steps=(
            PlannedStep(
                id="ok",
                title="OK",
                phase=StepPhase.SYSTEM_CONFIG,
                commands=(),
                destructive=False,
                description="d",
            ),
        ),
    )
    require_destructive_confirmation(plan, assume_yes=False, force=False, prompt=lambda _: True)


def test_user_says_no_raises() -> None:
    with pytest.raises(EnvErr, match="declined"):
        require_destructive_confirmation(
            _plan(), assume_yes=False, force=False, prompt=lambda _: False
        )


def test_mounts_summary_in_prompt() -> None:
    captured: list[str] = []

    def prompt(text: str) -> bool:
        captured.append(text)
        return True

    require_destructive_confirmation(
        _plan(),
        assume_yes=False,
        force=False,
        prompt=prompt,
        mounts_summary=("/mnt/data", "/srv"),
    )
    assert any("/mnt/data" in t and "/srv" in t for t in captured)


def test_no_mounts_summary_keeps_existing_prompt() -> None:
    captured: list[str] = []

    def prompt(text: str) -> bool:
        captured.append(text)
        return True

    require_destructive_confirmation(_plan(), assume_yes=False, force=False, prompt=prompt)
    assert captured
    assert "/mnt/data" not in captured[0]


def test_existing_filesystems_surfaced_in_prompt() -> None:
    captured: list[str] = []

    def prompt(text: str) -> bool:
        captured.append(text)
        return True

    require_destructive_confirmation(
        _plan(),
        assume_yes=False,
        force=False,
        prompt=prompt,
        existing_filesystems=(("sda1", "vfat"), ("sda2", "btrfs")),
    )
    assert captured
    text = captured[0]
    assert "sda1=vfat" in text
    assert "sda2=btrfs" in text
    # btrfs presence triggers the snapshots warning.
    assert "snapper" in text.lower() or "subvolume" in text.lower()
