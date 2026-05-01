"""Shared install-pipeline assembly used by the CLI and the TUI.

The :func:`build_install_pipeline_steps` helper produces the same
step list that ``getarch install`` runs (disk-busy guard, network
bootstrap, runtime preflight, disk wipe, planned steps, audit log),
honouring container-mode skips. Both entry points (``install`` CLI and
``tui --execute --no-dry-run``) call into it so safety guards never
diverge between the two surfaces.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from getarch.config.schema.v1 import Config
from getarch.domain.plan import InstallPlan
from getarch.execution.logging_runner import LoggingRunner
from getarch.execution.real_runner import RealRunner
from getarch.installers.base import PlannedStepExecutor
from getarch.installers.preflight import (
    AuditLogStep,
    DiskBusyGuardStep,
    DiskWipeStep,
    RuntimeNetworkBootstrapStep,
    RuntimePreflightStep,
)
from getarch.system.block_devices import LsblkBlockDevices


def build_install_pipeline_steps(
    plan: InstallPlan,
    *,
    cfg: Config,
    audit_runner: LoggingRunner,
    mount_root: Path,
    dry_run: bool,
    skip_runtime_preflight: bool = False,
) -> Sequence[object]:
    """Assemble the full install pipeline (guards + planned + audit).

    Mirrors what ``getarch install`` runs. The TUI live-execute screen
    calls into this so the live-install and CLI-install paths can never
    drift apart on safety surface.
    """
    container_mode = cfg.firmware == "container"
    steps: list[object] = []
    # Disk-busy guard is meaningless in a chroot/container.
    if not dry_run and not container_mode:
        steps.append(
            DiskBusyGuardStep(
                block_devices=LsblkBlockDevices(runner=RealRunner()),
                target_disk_path=cfg.disk.path,
            ),
        )
    if not dry_run and not container_mode and cfg.network.bootstrap is not None:
        bootstrap = cfg.network.bootstrap
        steps.append(
            RuntimeNetworkBootstrapStep(
                backend=bootstrap.kind,
                device=bootstrap.device,
                ssid=getattr(bootstrap, "ssid", None),
                psk=getattr(bootstrap, "psk", None),
                username=getattr(bootstrap, "username", None),
                password=getattr(bootstrap, "password", None),
                cert_path=getattr(bootstrap, "cert_path", None),
                private_key_path=getattr(bootstrap, "private_key_path", None),
                ca_cert_path=getattr(bootstrap, "ca_cert_path", None),
                eap_method=getattr(bootstrap, "eap_method", "PEAP"),
                config_path=getattr(bootstrap, "config_path", None),
            ),
        )
    if not skip_runtime_preflight and not dry_run and not container_mode:
        steps.append(RuntimePreflightStep())
    log_path = mount_root / "var/log/getarch.log"
    audit_step: object | None = (
        AuditLogStep(audit_runner=audit_runner, log_path=log_path)
        if not dry_run
        else None
    )
    wipe_step: object | None = (
        DiskWipeStep(target_disk_path=cfg.disk.path)
        if not dry_run and not container_mode and cfg.disk.wipe_before
        else None
    )
    for planned in plan.steps:
        # Wipe runs immediately before partitioning so all
        # non-destructive prerequisites have already succeeded.
        if wipe_step is not None and planned.id == "partitioning":
            steps.append(wipe_step)
            wipe_step = None
        if audit_step is not None and planned.id == "cleanup":
            steps.append(audit_step)
            audit_step = None
        steps.append(PlannedStepExecutor(planned=planned))
    if audit_step is not None:
        # No cleanup step (unusual): still flush the audit log.
        steps.append(audit_step)
    return tuple(steps)
