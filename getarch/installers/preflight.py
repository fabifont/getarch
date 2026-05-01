"""Runtime-only preflight steps that run inside the install pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.errors import EnvironmentError as _EnvErr
from getarch.execution.command import Command
from getarch.execution.context import ExecutionContext
from getarch.execution.logging_runner import LoggingRunner
from getarch.execution.result import CommandResult, StepResult, StepStatus
from getarch.system.discovery import BlockDeviceProvider


class RuntimePreflightStep:
    id: str = "runtime-preflight"
    title: str = "Runtime preflight"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        commands = (
            Command(
                argv=("timedatectl", "set-ntp", "true"),
                description="enable NTP",
            ),
            Command(
                argv=("pacman", "-Sy", "--noconfirm", "archlinux-keyring"),
                description="refresh archlinux-keyring",
            ),
            Command(argv=("pacman-key", "--init"), description="init pacman keyring"),
            Command(
                argv=("pacman-key", "--populate", "archlinux"),
                description="populate pacman keyring with arch master keys",
            ),
        )
        results: list[CommandResult] = [
            ctx.runner.run(c, chroot_path=str(ctx.mount_root)) for c in commands
        ]
        status = StepStatus.SUCCEEDED if all(r.ok for r in results) else StepStatus.FAILED
        return StepResult(step_id=self.id, status=status, commands=tuple(results))


@dataclass(frozen=True, slots=True)
class DiskBusyGuardStep:
    """Refresh-mount-state guard inserted before any destructive plan step.

    Holds its own :class:`BlockDeviceProvider` so the check uses the real
    system view independently of ``ExecutionContext.runner`` (which may be a
    :class:`DryRunner`). Cannot be bypassed by ``--skip-environment-preflight``
    or ``--yes``/``--force`` — refusing is the whole job.
    """

    block_devices: BlockDeviceProvider
    target_disk_path: str
    id: str = "disk-busy-guard"
    title: str = "Disk-busy guard"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        del ctx
        mounts = self.block_devices.target_disk_busy(self.target_disk_path)
        if mounts:
            raise _EnvErr(
                f"target disk {self.target_disk_path} has mounted partitions: "
                f"{', '.join(mounts)}. Refusing to proceed.",
            )
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED, commands=())


@dataclass(frozen=True, slots=True)
class RuntimeNetworkBootstrapStep:
    """Bring up wifi/wired before the runtime preflight needs internet.

    Wraps ``iwctl station <dev> connect <ssid>`` (with PSK piped in) for
    wifi or ``dhcpcd <dev>`` for wired DHCP. Inserted by the install
    command immediately *before* :class:`RuntimePreflightStep`.
    """

    backend: str
    device: str
    ssid: str | None = None
    psk: str | None = None
    id: str = "runtime-network-bootstrap"
    title: str = "Bring up network"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        results: list[CommandResult] = []
        if self.backend == "iwctl":
            if not self.ssid or self.psk is None:
                raise _EnvErr("wifi bootstrap requires ssid and psk")
            # Drop the PSK into iwd's per-network state file (mode 0600)
            # so it never appears in argv / /proc. iwctl + iwd then
            # connect without --passphrase.
            psk_path = f"/var/lib/iwd/{self.ssid}.psk"
            results.append(
                ctx.runner.run(
                    Command(
                        argv=("install", "-Dm600", "/dev/stdin", psk_path),
                        input=f"[Security]\nPassphrase = {self.psk}\n",
                        sensitive=True,
                        description=f"write {psk_path}",
                    ),
                ),
            )
            results.append(
                ctx.runner.run(
                    Command(
                        argv=(
                            "iwctl",
                            "station",
                            self.device,
                            "connect",
                            self.ssid,
                        ),
                        description=(
                            f"connect {self.device} to wifi {self.ssid}"
                        ),
                    ),
                ),
            )
        elif self.backend == "dhcp":
            results.append(
                ctx.runner.run(
                    Command(
                        argv=("dhcpcd", self.device),
                        description=f"start dhcpcd on {self.device}",
                    ),
                ),
            )
        else:
            raise _EnvErr(f"unknown bootstrap backend {self.backend!r}")
        status = (
            StepStatus.SUCCEEDED if all(r.ok for r in results) else StepStatus.FAILED
        )
        return StepResult(step_id=self.id, status=status, commands=tuple(results))


@dataclass(frozen=True, slots=True)
class AuditLogStep:
    """Persist :class:`LoggingRunner` lines to the target before cleanup.

    Inserted by the install command immediately before the planner's
    cleanup step so the audit trail lands inside the new system, not on
    the live ISO. Holds a reference to the runner so it can read the
    current buffer when executed.
    """

    audit_runner: LoggingRunner
    log_path: Path
    id: str = "audit-log"
    title: str = "Persist audit log"
    destructive: bool = False

    def execute(self, ctx: ExecutionContext) -> StepResult:
        del ctx
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.write_text(self.audit_runner.render(), encoding="utf-8")
        except OSError as exc:
            raise _EnvErr(
                f"failed to write audit log to {self.log_path}: {exc}",
            ) from exc
        return StepResult(step_id=self.id, status=StepStatus.SUCCEEDED, commands=())
