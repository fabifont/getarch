"""Hypothesis-driven planner invariants.

Generates random *valid* config payloads (built from the example as a
seed) and asserts properties of the resulting plan. The strategies stay
inside the schema's accepted ranges so semantic validation does not
short-circuit before the planner runs.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.config.semantic import validate_semantics
from getarch.domain.disk import Disk, DiskPath
from getarch.domain.plan import StepPhase
from getarch.planning.planner import Planner

_BTRFS_HOOKS: list[str] = [
    "base",
    "systemd",
    "autodetect",
    "modconf",
    "kms",
    "keyboard",
    "sd-vconsole",
    "block",
    "sd-encrypt",
    "filesystems",
    "fsck",
]
_DEFAULT_HOOKS: list[str] = [
    "base",
    "udev",
    "autodetect",
    "modconf",
    "block",
    "filesystems",
    "fsck",
]


def _payload_from(
    *,
    fs: str,
    encrypted: bool,
    swap_kind: str,
    bootloader: str,
    initramfs: str,
    timeout: int,
) -> dict[str, object]:
    base = deepcopy(EXAMPLES["minimal-ext4"])
    base["filesystem"] = {"kind": fs, "label": "system"}
    if encrypted:
        base["encryption"] = {"kind": "luks2", "password": "x"}
        base["initramfs"] = {"generator": initramfs, "hooks": _BTRFS_HOOKS}
    else:
        base["encryption"] = {"kind": "none"}
        base["initramfs"] = {
            "generator": initramfs,
            "hooks": [] if initramfs == "dracut" else _DEFAULT_HOOKS,
        }
    if swap_kind == "swapfile":
        base["swap"] = {"kind": "swapfile", "size_mib": 1024}
    elif swap_kind == "zram":
        base["swap"] = {"kind": "zram", "zram_size_mib": 1024}
    else:
        base["swap"] = {"kind": "none"}
    base["bootloader"] = {
        "kind": bootloader,
        "entry_id": "arch",
        "timeout_seconds": timeout,
    }
    return base


_VALID_COMBOS = st.fixed_dictionaries(
    {
        "fs": st.sampled_from(["ext4", "btrfs", "xfs", "f2fs"]),
        "encrypted": st.booleans(),
        "swap_kind": st.sampled_from(["none", "swapfile", "zram"]),
        "bootloader": st.sampled_from(["systemd-boot", "grub", "uki"]),
        "initramfs": st.sampled_from(["mkinitcpio", "dracut"]),
        "timeout": st.integers(min_value=0, max_value=120),
    },
)


@settings(max_examples=80, deadline=None)
@given(_VALID_COMBOS)
def test_planner_invariants(combo: dict[str, object]) -> None:
    encrypted = bool(combo["encrypted"])
    fs = str(combo["fs"])
    timeout_raw = combo["timeout"]
    assert isinstance(timeout_raw, int)
    # btrfs subvolumes are required for encrypted btrfs (default-injected).
    payload = _payload_from(
        fs=fs,
        encrypted=encrypted,
        swap_kind=str(combo["swap_kind"]),
        bootloader=str(combo["bootloader"]),
        initramfs=str(combo["initramfs"]),
        timeout=timeout_raw,
    )
    cfg = Config.model_validate(payload)
    validate_semantics(cfg)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**33),
        mount_root=Path("/mnt"),
    )

    # Invariant 1: step IDs are unique.
    ids = [s.id for s in plan.steps]
    assert len(set(ids)) == len(ids), f"duplicate step IDs: {ids}"

    # Invariant 2: destructive steps are exactly the early phases.
    destructive_phases = {
        StepPhase.PARTITIONING,
        StepPhase.ENCRYPTION,
        StepPhase.FILESYSTEMS,
    }
    for step in plan.steps:
        if step.destructive:
            assert step.phase in destructive_phases, (
                f"destructive step {step.id} in non-destructive phase {step.phase}"
            )

    # Invariant 3: every command has a non-empty argv.
    for step in plan.steps:
        for cmd in step.commands:
            assert cmd.argv, f"empty argv in {step.id}"
            assert isinstance(cmd.argv[0], str) and cmd.argv[0]

    # Invariant 4: phase order is monotonically non-decreasing on the
    # phase enum's declaration order.
    phase_order = list(StepPhase)
    indices = [phase_order.index(s.phase) for s in plan.steps]
    assert indices == sorted(indices), (
        f"phases out of order: {[s.phase.value for s in plan.steps]}"
    )
