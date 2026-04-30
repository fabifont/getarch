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
    text += " Proceed? "
    if not prompt(text):
        raise _EnvErr("user declined destructive operation")
