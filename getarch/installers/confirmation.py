"""Destructive confirmation gate."""

from __future__ import annotations

from collections.abc import Callable

from getarch.domain.plan import InstallPlan
from getarch.errors import EnvironmentError as _EnvErr

ConfirmFn = Callable[[str], bool]


def require_destructive_confirmation(
    plan: InstallPlan,
    *,
    assume_yes: bool,
    force: bool,
    prompt: ConfirmFn,
    mounts_summary: tuple[str, ...] = (),
    existing_filesystems: tuple[tuple[str, str], ...] = (),
) -> None:
    if assume_yes or force:
        return
    if not plan.has_destructive_steps:
        return
    summary = ", ".join(s.id for s in plan.destructive_steps)
    text = f"Plan contains destructive steps ({summary})."
    if mounts_summary:
        text += (
            f" WARNING: target disk has mounted partitions: "
            f"{', '.join(mounts_summary)}."
        )
    if existing_filesystems:
        rendered = ", ".join(f"{name}={fs}" for name, fs in existing_filesystems)
        text += f" Existing filesystems on target disk will be wiped: {rendered}."
        if any(fs == "btrfs" for _name, fs in existing_filesystems):
            text += (
                " (btrfs detected — any subvolumes / snapper snapshots on "
                "this disk will be lost.)"
            )
    text += " Proceed? "
    if not prompt(text):
        raise _EnvErr("user declined destructive operation")
