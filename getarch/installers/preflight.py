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
class DiskWipeStep:
    """Best-effort wipe of the target disk before partitioning.

    Runs ``wipefs -a -f`` (clears every signature) and ``blkdiscard -f``
    (best-effort: HDDs return non-zero, which is fine — we run with
    ``check=False``). Inserted between :class:`DiskBusyGuardStep` and
    runtime network/preflight only when ``cfg.disk.wipe_before`` is true.
    """

    target_disk_path: str
    id: str = "disk-wipe"
    title: str = "Wipe target disk signatures"
    destructive: bool = True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        results: list[CommandResult] = [
            ctx.runner.run(
                Command(
                    argv=("wipefs", "-a", "-f", self.target_disk_path),
                    description=f"clear filesystem signatures on {self.target_disk_path}",
                ),
            ),
            ctx.runner.run(
                Command(
                    argv=("blkdiscard", "-f", self.target_disk_path),
                    check=False,
                    description=(
                        f"discard blocks on {self.target_disk_path} (best-effort)"
                    ),
                ),
            ),
        ]
        # blkdiscard non-zero is acceptable; only fail if wipefs failed.
        wipefs_ok = results[0].ok
        status = StepStatus.SUCCEEDED if wipefs_ok else StepStatus.FAILED
        return StepResult(step_id=self.id, status=status, commands=tuple(results))


@dataclass(frozen=True, slots=True)
class RuntimeNetworkBootstrapStep:
    """Bring up wifi/wired/vpn before the runtime preflight needs internet.

    Backends:

    * ``iwctl`` — WPA2-PSK via ``iwctl station <dev> connect <ssid>``
      (passphrase dropped into ``/var/lib/iwd/<ssid>.psk``).
    * ``dhcp`` — wired ``dhcpcd <dev>``.
    * ``iwctl-eap`` — WPA2-Enterprise via iwd 8021x profile under
      ``/var/lib/iwd/<ssid>.8021x`` (PEAP/TTLS use password, TLS uses
      cert + key), then ``iwctl station <dev> connect <ssid>``.
    * ``wireguard`` — bring an existing ``wg-quick`` config up before the
      runtime preflight (so pacman can reach a private mirror over the
      tunnel).

    Inserted by the install command immediately *before*
    :class:`RuntimePreflightStep`.
    """

    backend: str
    device: str
    ssid: str | None = None
    psk: str | None = None
    username: str | None = None
    password: str | None = None
    cert_path: str | None = None
    private_key_path: str | None = None
    ca_cert_path: str | None = None
    eap_method: str = "PEAP"
    config_path: str | None = None
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
        elif self.backend == "iwctl-eap":
            if not self.ssid or not self.username:
                raise _EnvErr(
                    "iwctl-eap bootstrap requires ssid and username",
                )
            profile_path = f"/var/lib/iwd/{self.ssid}.8021x"
            profile = self._render_8021x_profile()
            results.append(
                ctx.runner.run(
                    Command(
                        argv=("install", "-Dm600", "/dev/stdin", profile_path),
                        input=profile,
                        sensitive=True,
                        description=f"write {profile_path}",
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
                            f"connect {self.device} to wifi {self.ssid} (EAP)"
                        ),
                    ),
                ),
            )
        elif self.backend == "wireguard":
            if not self.config_path:
                raise _EnvErr("wireguard bootstrap requires config_path")
            results.append(
                ctx.runner.run(
                    Command(
                        argv=("wg-quick", "up", self.config_path),
                        description=f"bring up wireguard tunnel {self.device}",
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

    def _render_8021x_profile(self) -> str:
        method = self.eap_method
        lines: list[str] = ["[Security]", f"EAP-Method={method}"]
        if method == "TLS":
            if not self.cert_path or not self.private_key_path:
                raise _EnvErr(
                    "iwctl-eap TLS requires cert_path and private_key_path",
                )
            lines.extend(
                [
                    f"EAP-Identity={self.username}",
                    f"EAP-TLS-ClientCert={self.cert_path}",
                    f"EAP-TLS-ClientKey={self.private_key_path}",
                ],
            )
            if self.ca_cert_path:
                lines.append(f"EAP-TLS-CACert={self.ca_cert_path}")
        elif method in {"PEAP", "TTLS"}:
            if not self.password:
                raise _EnvErr(
                    f"iwctl-eap {method} requires password",
                )
            phase2 = "MSCHAPV2" if method == "PEAP" else "Token-PAP"
            prefix = "EAP-PEAP" if method == "PEAP" else "EAP-TTLS"
            lines.extend(
                [
                    "EAP-Identity=anonymous",
                    f"{prefix}-Phase2-Method={phase2}",
                    f"{prefix}-Phase2-Identity={self.username}",
                    f"{prefix}-Phase2-Password={self.password}",
                ],
            )
            # Without a CA cert, recent iwd versions refuse PEAP/TTLS
            # auth as a security default. Honour an explicit user-supplied
            # CA cert; otherwise the operator must drop it via the system
            # trust store before bootstrapping.
            if self.ca_cert_path:
                lines.append(f"{prefix}-CACert={self.ca_cert_path}")
        else:
            raise _EnvErr(f"unsupported EAP method {method!r}")
        return "\n".join(lines) + "\n"


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
