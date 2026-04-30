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


def test_planner_microcode_auto_intel_appends_package() -> None:
    plan = Planner().build(
        cfg=Config.model_validate(EXAMPLES["minimal-ext4"]),
        disk=_disk(),
        mount_root=Path("/mnt"),
        cpu_vendor="GenuineIntel",
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "intel-ucode" in pkgs_step.commands[0].argv


def test_planner_microcode_auto_amd_appends_package() -> None:
    plan = Planner().build(
        cfg=Config.model_validate(EXAMPLES["minimal-ext4"]),
        disk=_disk(),
        mount_root=Path("/mnt"),
        cpu_vendor="AuthenticAMD",
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "amd-ucode" in pkgs_step.commands[0].argv


def test_planner_microcode_auto_unknown_skips() -> None:
    plan = Planner().build(
        cfg=Config.model_validate(EXAMPLES["minimal-ext4"]),
        disk=_disk(),
        mount_root=Path("/mnt"),
        cpu_vendor=None,
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "intel-ucode" not in pkgs_step.commands[0].argv
    assert "amd-ucode" not in pkgs_step.commands[0].argv


def test_planner_microcode_explicit_overrides_vendor() -> None:
    cfg_dict = {**EXAMPLES["minimal-ext4"], "microcode": {"kind": "amd"}}
    plan = Planner().build(
        cfg=Config.model_validate(cfg_dict),
        disk=_disk(),
        mount_root=Path("/mnt"),
        cpu_vendor="GenuineIntel",
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    assert "amd-ucode" in pkgs_step.commands[0].argv
    assert "intel-ucode" not in pkgs_step.commands[0].argv


def test_planner_emits_mirrors_step_when_reflector() -> None:
    cfg_dict = {
        **EXAMPLES["minimal-ext4"],
        "mirrors": {
            "strategy": "reflector",
            "reflector_args": ["--country", "Italy"],
        },
    }
    plan = Planner().build(
        cfg=Config.model_validate(cfg_dict),
        disk=_disk(),
        mount_root=Path("/mnt"),
    )
    ids = [s.id for s in plan.steps]
    assert "mirrors" in ids
    assert ids.index("mirrors") < ids.index("packages")


def test_planner_skips_mirrors_step_when_keep() -> None:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    assert "mirrors" not in {s.id for s in plan.steps}


def test_planner_emits_swap_step_when_swapfile() -> None:
    cfg_dict = {
        **EXAMPLES["minimal-ext4"],
        "swap": {"kind": "swapfile", "size_mib": 2048},
    }
    plan = Planner().build(
        cfg=Config.model_validate(cfg_dict),
        disk=_disk(),
        mount_root=Path("/mnt"),
    )
    ids = [s.id for s in plan.steps]
    assert "swap" in ids
    swap_idx = ids.index("swap")
    assert ids.index("mounting") < swap_idx < ids.index("packages")


def test_planner_skips_swap_step_when_none() -> None:
    cfg = Config.model_validate(EXAMPLES["minimal-ext4"])
    plan = Planner().build(cfg=cfg, disk=_disk(), mount_root=Path("/mnt"))
    assert "swap" not in {s.id for s in plan.steps}
