from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.domain.plan import InstallPlan, StepPhase
from getarch.planning.planner import Planner


def _disk(path: str = "/dev/sda") -> Disk:
    return Disk(path=DiskPath(Path(path)), size_bytes=2**33)


def test_planner_emits_phases_in_order() -> None:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    assert isinstance(plan, InstallPlan)
    phases = [s.phase for s in plan.steps]
    expected_order = [
        StepPhase.PARTITIONING,
        StepPhase.FILESYSTEMS,
        StepPhase.MOUNTING,
        StepPhase.PACKAGES,
        StepPhase.FSTAB,
        StepPhase.SYSTEM_CONFIG,
        StepPhase.INITRAMFS,
        StepPhase.BOOTLOADER,
        StepPhase.SERVICES,
        StepPhase.USERS,
        StepPhase.CLEANUP,
    ]
    indices = [phases.index(p) for p in expected_order if p in phases]
    assert indices == sorted(indices)


def test_planner_includes_encryption_when_luks2() -> None:
    cfg = Config.model_validate(EXAMPLES["encrypted-btrfs"])
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    phases = {s.phase for s in plan.steps}
    assert StepPhase.ENCRYPTION in phases


def test_destructive_steps_flagged() -> None:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    assert plan.has_destructive_steps
    destructive_ids = {s.id for s in plan.destructive_steps}
    assert "partitioning" in destructive_ids
