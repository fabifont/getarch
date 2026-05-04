"""End-to-end QEMU smoke runner for getarch.

Boots the upstream Arch ISO inside QEMU/KVM, shares a workspace with the
guest via virtfs, sends a single ``mount -t 9p ... && bash run_install.sh``
command via the QEMU monitor, then waits for the sentinel file the guest
writes. After install completes, optionally reboots and asserts the new
system also boots.

Designed for the per-PR matrix workflow under ``.github/workflows/qemu.yml``;
also runnable locally if you have ``qemu-system-x86_64``, ``OVMF``, and
sufficient RAM.

Usage:
    python test_resources/qemu_smoke.py \\
        --iso /path/to/archlinux.iso \\
        --ovmf-code /usr/share/OVMF/OVMF_CODE.fd \\
        --ovmf-vars /usr/share/OVMF/OVMF_VARS.fd \\
        --workspace /tmp/qemu-smoke \\
        --config test_resources/configs/ext4-systemd-boot.json \\
        --zipapp dist/getarch.pyz \\
        [--no-kvm] [--reboot-check]

Exit codes:
    0  install + (optional) reboot check passed
    1  install timed out or failed
    2  reboot check failed
    3  orchestration error (QEMU did not start, virtfs broken, ...)
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from pathlib import Path

# Tuned for full matrix on KVM. Generous because pacstrap downloads packages.
_INSTALL_TIMEOUT_SECONDS = 30 * 60
_AUTOLOGIN_TIMEOUT_SECONDS = 5 * 60
_REBOOT_TIMEOUT_SECONDS = 10 * 60
_POLL_INTERVAL_SECONDS = 5
_SENDKEY_INTERVAL_SECONDS = 0.05

# Maps ASCII characters to QEMU "sendkey" tokens.
_SENDKEY_MAP: dict[str, str] = {
    " ": "spc",
    ".": "dot",
    ",": "comma",
    "/": "slash",
    "-": "minus",
    "=": "equal",
    "_": "shift-minus",
    "+": "shift-equal",
    "(": "shift-9",
    ")": "shift-0",
    "[": "bracket_left",
    "]": "bracket_right",
    "{": "shift-bracket_left",
    "}": "shift-bracket_right",
    ":": "shift-semicolon",
    ";": "semicolon",
    "'": "apostrophe",
    '"': "shift-apostrophe",
    "<": "shift-comma",
    ">": "shift-dot",
    "?": "shift-slash",
    "!": "shift-1",
    "@": "shift-2",
    "#": "shift-3",
    "$": "shift-4",
    "%": "shift-5",
    "^": "shift-6",
    "&": "shift-7",
    "*": "shift-8",
    "|": "shift-backslash",
    "\\": "backslash",
    "`": "grave_accent",
    "~": "shift-grave_accent",
    "\n": "ret",
    "\t": "tab",
}


def _char_to_keys(ch: str) -> list[str]:
    if ch in _SENDKEY_MAP:
        return [_SENDKEY_MAP[ch]]
    if ch.isdigit():
        return [ch]
    if ch.isalpha():
        return [f"shift-{ch.lower()}" if ch.isupper() else ch]
    raise ValueError(f"no QEMU sendkey mapping for character {ch!r}")


class _QemuMonitor:
    """Thin wrapper around the QEMU human monitor over a unix socket."""

    def __init__(self, sock_path: Path) -> None:
        self.sock_path = sock_path
        self._sock: socket.socket | None = None

    def connect(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        last_exc: OSError | None = None
        while time.monotonic() < deadline:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(str(self.sock_path))
                self._sock = s
                # Drain banner.
                self._drain(0.5)
                return
            except OSError as exc:
                last_exc = exc
                time.sleep(0.5)
        raise RuntimeError(
            f"could not connect to QEMU monitor at {self.sock_path}: {last_exc}",
        )

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None

    def send(self, command: str) -> None:
        if self._sock is None:
            raise RuntimeError("monitor not connected")
        self._sock.sendall((command + "\n").encode("utf-8"))
        self._drain(0.1)

    def sendkey(self, key: str) -> None:
        self.send(f"sendkey {key}")
        time.sleep(_SENDKEY_INTERVAL_SECONDS)

    def type_text(self, text: str) -> None:
        for ch in text:
            for key in _char_to_keys(ch):
                self.sendkey(key)

    def system_reset(self) -> None:
        self.send("system_reset")

    def quit(self) -> None:
        with contextlib.suppress(Exception):
            self.send("quit")

    def _drain(self, seconds: float) -> bytes:
        if self._sock is None:
            return b""
        self._sock.settimeout(seconds)
        chunks: list[bytes] = []
        try:
            while True:
                data = self._sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
        except (OSError, TimeoutError):
            pass
        return b"".join(chunks)


class _SerialPort:
    """Bidirectional access to the guest's ttyS0 via a unix socket.

    QEMU's ``-serial file:...`` is read-only and one-way; ``sendkey`` on
    the monitor delivers events to the framebuffer keyboard, not to the
    serial port. To both *watch* the serial output (existing
    ``_wait_for_serial_pattern`` polls a file on disk) and *write* into
    the serial port (so we can drive the manual login prompt that
    archiso shows on ttyS0), we expose ttyS0 via a unix socket and run a
    background thread that tees socket reads into the same on-disk log
    the polling reader expects.
    """

    def __init__(self, sock_path: Path, log_path: Path) -> None:
        self.sock_path = sock_path
        self.log_path = log_path
        self._sock: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()

    def connect(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        last_exc: OSError | None = None
        while time.monotonic() < deadline:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(str(self.sock_path))
            except OSError as exc:
                last_exc = exc
                time.sleep(0.5)
            else:
                self._sock = s
                self._sock.settimeout(0.5)
                self._reader = threading.Thread(
                    target=self._tee_loop, daemon=True,
                )
                self._reader.start()
                return
        raise RuntimeError(
            f"could not connect to serial socket {self.sock_path}: {last_exc}",
        )

    def write_line(self, line: str) -> None:
        """Send ``line`` followed by ``\\n`` over the serial port."""
        if self._sock is None:
            raise RuntimeError("serial port not connected")
        payload = (line + "\n").encode("utf-8")
        self._sock.sendall(payload)

    def close(self) -> None:
        self._stop.set()
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                self._sock.close()
            self._sock = None
        if self._reader is not None:
            self._reader.join(timeout=2.0)
            self._reader = None

    def _tee_loop(self) -> None:
        # Open the log in append mode so anything QEMU wrote before our
        # connect (loader output, kernel boot) is preserved.
        with self.log_path.open("ab", buffering=0) as fp:
            while not self._stop.is_set():
                if self._sock is None:
                    return
                try:
                    chunk = self._sock.recv(4096)
                except TimeoutError:
                    continue
                except OSError:
                    return
                if not chunk:
                    return
                with contextlib.suppress(OSError):
                    fp.write(chunk)


def _iso_volume_label(iso: Path) -> str:
    """Read the ISO9660 volume id (e.g. ``ARCH_202605``) via ``isoinfo``."""
    result = subprocess.run(  # noqa: S603
        ["isoinfo", "-d", "-i", str(iso)],  # noqa: S607
        capture_output=True, text=True, check=True,
    )
    for line in result.stdout.splitlines():
        if line.lower().startswith("volume id:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"could not read volume id from {iso}")


def _extract_iso_boot_assets(iso: Path, dest: Path) -> dict[str, Path]:
    """Extract vmlinuz + initramfs (+ ucode if present) from ``iso``.

    Skipping GRUB by passing ``-kernel`` + ``-initrd`` directly to QEMU
    sidesteps the previously-broken GRUB-edit dance: keystrokes via
    ``sendkey`` were dropping the Ctrl modifier on OVMF + virtio-kbd, so
    Ctrl+X / F10 never reached GRUB and the kernel never picked up
    ``console=ttyS0``. With direct boot we control the cmdline outright.
    """
    dest.mkdir(parents=True, exist_ok=True)
    paths = {
        "vmlinuz": "arch/boot/x86_64/vmlinuz-linux",
        "initramfs": "arch/boot/x86_64/initramfs-linux.img",
        "intel_ucode": "arch/boot/x86_64/intel-ucode.img",
        "amd_ucode": "arch/boot/x86_64/amd-ucode.img",
    }
    extracted: dict[str, Path] = {}
    for key, member in paths.items():
        target = dest / Path(member).name
        try:
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "bsdtar", "-xf", str(iso),
                    "-C", str(dest), "--strip-components=3",
                    member,
                ],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError:
            # Ucode files are optional (vendor mismatch is fine; QEMU runs
            # qemu64 anyway). vmlinuz + initramfs are required.
            if key in {"vmlinuz", "initramfs"}:
                raise
            continue
        extracted[key] = target
    return extracted


def _build_install_qemu_argv(
    *,
    iso: Path,
    disk: Path,
    workspace: Path,
    ovmf_code: Path,
    ovmf_vars: Path,
    monitor_sock: Path,
    serial_sock: Path,
    use_kvm: bool,
    memory_mib: int,
    cpus: int,
    display: str = "none",
    kernel: Path | None = None,
    initrds: tuple[Path, ...] = (),
    cmdline: str = "",
) -> list[str]:
    """QEMU argv for the *install* phase: ISO attached, virtfs share live."""

    argv = [
        "qemu-system-x86_64",
        "-machine", "q35",
        "-cpu", "host" if use_kvm else "qemu64",
        "-smp", str(cpus),
        "-m", f"{memory_mib}M",
        "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive", f"if=pflash,format=raw,file={ovmf_vars}",
        "-drive", f"file={disk},if=virtio,format=qcow2",
        "-cdrom", str(iso),
        "-virtfs",
        (
            f"local,path={workspace},mount_tag=shared,security_model=mapped,"
            "id=shared"
        ),
        "-net", "user",
        "-net", "nic,model=virtio",
        "-monitor", f"unix:{monitor_sock},server,nowait",
        "-chardev", f"socket,id=serial0,path={serial_sock},server=on,wait=off",
        "-serial", "chardev:serial0",
        "-display", display,
        "-no-reboot",
    ]
    if kernel is not None:
        # Direct boot: bypass GRUB entirely. QEMU's -initrd accepts a
        # comma-separated list (concatenated by QEMU at boot) so we feed
        # ucode images first, then the real initramfs — same order GRUB
        # uses.
        argv.extend(["-kernel", str(kernel)])
        if initrds:
            argv.extend(["-initrd", ",".join(str(p) for p in initrds)])
        if cmdline:
            argv.extend(["-append", cmdline])
    else:
        argv.extend(["-boot", "order=d,menu=off"])
    if use_kvm:
        argv.insert(1, "-enable-kvm")
    return argv


def _build_boot_qemu_argv(
    *,
    disk: Path,
    ovmf_code: Path,
    ovmf_vars: Path,
    monitor_sock: Path,
    serial_log: Path,
    use_kvm: bool,
    memory_mib: int,
    cpus: int,
    display: str = "none",
) -> list[str]:
    """QEMU argv for the *post-install boot verification* phase.

    No ISO attached — firmware boots from the installed disk only. No
    virtfs either; verification is done purely via the serial log to keep
    the surface small.
    """

    argv = [
        "qemu-system-x86_64",
        "-machine", "q35",
        "-cpu", "host" if use_kvm else "qemu64",
        "-smp", str(cpus),
        "-m", f"{memory_mib}M",
        "-drive", f"if=pflash,format=raw,readonly=on,file={ovmf_code}",
        "-drive", f"if=pflash,format=raw,file={ovmf_vars}",
        "-drive", f"file={disk},if=virtio,format=qcow2",
        "-boot", "order=c,menu=off",
        "-net", "user",
        "-net", "nic,model=virtio",
        "-monitor", f"unix:{monitor_sock},server,nowait",
        "-serial", f"file:{serial_log}",
        "-display", display,
        "-no-reboot",
    ]
    if use_kvm:
        argv.insert(1, "-enable-kvm")
    return argv


def _wait_for_serial_pattern(
    serial_log: Path,
    needles: Iterable[bytes],
    timeout: float,
) -> bytes | None:
    """Poll ``serial_log`` until any of ``needles`` appears or timeout."""

    deadline = time.monotonic() + timeout
    seen_size = 0
    needles_t = tuple(needles)
    while time.monotonic() < deadline:
        try:
            data = serial_log.read_bytes()
        except FileNotFoundError:
            data = b""
        if len(data) > seen_size:
            window = data[seen_size:]
            for needle in needles_t:
                if needle in window:
                    return needle
            seen_size = len(data)
        time.sleep(_POLL_INTERVAL_SECONDS)
    return None


def _wait_for_sentinel(sentinel: Path, timeout: float) -> int | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sentinel.is_file():
            try:
                return int(sentinel.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                return None
        time.sleep(_POLL_INTERVAL_SECONDS)
    return None


def _stage_workspace(
    workspace: Path,
    *,
    config: Path,
    zipapp: Path,
    bootstrap: Path,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config, workspace / "config.json")
    shutil.copy2(zipapp, workspace / "getarch.pyz")
    shutil.copy2(bootstrap, workspace / "run_install.sh")
    (workspace / "run_install.sh").chmod(0o755)
    # Pre-create the sentinels so existence checks on host are unambiguous.
    for stale in ("install.exit", "install.log", "boot.exit"):
        path = workspace / stale
        if path.exists():
            path.unlink()


_READY_TOKEN = "__GETARCH_SERIAL_READY__"  # noqa: S105 — sentinel string, not a credential


def _drive_install(
    serial: _SerialPort,
    *,
    serial_log: Path,
    workspace: Path,
) -> int:
    """Drive the install over the serial port.

    Different archiso releases vary in whether they autologin root on
    ``serial-getty@ttyS0``. We unconditionally do the login dance:
    Arch ISO's root user has no password, so ``root\\n`` then an empty
    ``\\n`` always succeeds — and if autologin already fired, ``root``
    becomes a harmless ``bash: root: command not found`` and the empty
    line is a no-op.

    Bash prompts on the live ISO render ``root@archiso`` with ANSI
    color codes that split the literal across multiple bytes, so we
    don't try to detect the prompt directly. Instead, after the login
    dance, we send ``echo TOKEN`` and wait for the token to round-trip
    back through the serial log. Once we see our own echo we know the
    shell is at a prompt accepting commands.
    """
    if _wait_for_serial_pattern(
        serial_log,
        (b"archiso login:",),
        _AUTOLOGIN_TIMEOUT_SECONDS,
    ) is None:
        raise RuntimeError("timed out waiting for ISO login prompt")
    # Always perform the manual login dance. Empty password is correct
    # for the Arch live ISO root account.
    serial.write_line("root")
    time.sleep(1.0)
    serial.write_line("")
    time.sleep(2.0)
    # Use printf so bash interpolation produces a marker that ONLY a
    # real shell could emit. If login failed and we're back at agetty,
    # agetty would echo the raw command text (containing the token but
    # not the wrapped form) — so waiting for "BEGIN<token>END" forces
    # us to confirm a real shell, not a login-prompt echo.
    serial.write_line(f"printf 'BEGIN%sEND\\n' {_READY_TOKEN}")
    if _wait_for_serial_pattern(
        serial_log,
        (f"BEGIN{_READY_TOKEN}END".encode("ascii"),),
        timeout=60.0,
    ) is None:
        raise RuntimeError(
            "shell did not run printf marker; the login dance may have "
            "failed (check /tmp/.../serial.log for 'Login incorrect')",
        )
    serial.write_line(
        "mkdir -p /shared && mount -t 9p -o trans=virtio,version=9p2000.L "
        "shared /shared && bash /shared/run_install.sh",
    )
    rc = _wait_for_sentinel(workspace / "install.exit", _INSTALL_TIMEOUT_SECONDS)
    if rc is None:
        raise RuntimeError("timed out waiting for install sentinel")
    return rc


def _verify_disk_boot(
    *,
    disk: Path,
    ovmf_code: Path,
    ovmf_vars: Path,
    workspace: Path,
    serial_log: Path,
    use_kvm: bool,
    memory_mib: int,
    cpus: int,
    display: str = "none",
) -> bool:
    """Restart QEMU disk-only and assert the installed system reaches login.

    The install-phase QEMU is killed by the caller before we get here.
    Booting without ``-cdrom``/``-virtfs`` proves UEFI picks up the
    installed disk and userspace runs to a getty prompt. We do *not*
    attempt to mount any host share or run commands inside the guest:
    that surface area is what previously made the check unreliable.
    """

    monitor_sock = workspace / "monitor-boot.sock"
    serial_log.write_bytes(b"")
    qemu_argv = _build_boot_qemu_argv(
        disk=disk,
        ovmf_code=ovmf_code,
        ovmf_vars=ovmf_vars,
        monitor_sock=monitor_sock,
        serial_log=serial_log,
        use_kvm=use_kvm,
        memory_mib=memory_mib,
        cpus=cpus,
        display=display,
    )
    print("[qemu_smoke] booting installed disk:", " ".join(qemu_argv), flush=True)
    proc = subprocess.Popen(qemu_argv)
    monitor = _QemuMonitor(monitor_sock)
    try:
        monitor.connect(timeout=60.0)
        needle = _wait_for_serial_pattern(
            serial_log,
            (b"qemu-arch login:", b"Reached target Multi-User System"),
            _REBOOT_TIMEOUT_SECONDS,
        )
        return needle is not None
    finally:
        monitor.quit()
        monitor.close()
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def main() -> int:  # noqa: PLR0915, C901, PLR0912
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--ovmf-code", type=Path, required=True)
    parser.add_argument("--ovmf-vars", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--zipapp", type=Path, required=True)
    parser.add_argument(
        "--bootstrap",
        type=Path,
        default=Path(__file__).parent / "run_install.sh",
    )
    parser.add_argument("--disk-size", default="16G")
    parser.add_argument("--memory-mib", type=int, default=4096)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--no-kvm", action="store_true")
    parser.add_argument("--reboot-check", action="store_true")
    parser.add_argument(
        "--display",
        default="none",
        help=(
            "QEMU --display backend. Default 'none' (CI-friendly, no "
            "window). Pass 'gtk' / 'sdl' / 'cocoa' to watch the install "
            "live."
        ),
    )
    args = parser.parse_args()

    workspace: Path = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    disk = workspace / "disk.qcow2"
    monitor_sock = workspace / "monitor.sock"
    serial_log = workspace / "serial.log"
    serial_log.write_bytes(b"")

    if disk.exists():
        disk.unlink()
    subprocess.run(
        ["qemu-img", "create", "-f", "qcow2", str(disk), args.disk_size],
        check=True,
    )

    # Stage host-side workspace exposed via virtfs.
    share_dir = workspace / "share"
    _stage_workspace(
        share_dir,
        config=args.config,
        zipapp=args.zipapp,
        bootstrap=args.bootstrap,
    )

    # Extract kernel + initramfs from the ISO so QEMU can boot them
    # directly with our cmdline (skipping GRUB). The kernel still needs
    # to find the live rootfs on the cdrom; archiso looks for the
    # ISO9660 volume label via ``archisolabel=``.
    boot_assets_dir = workspace / "boot"
    boot_assets = _extract_iso_boot_assets(args.iso, boot_assets_dir)
    iso_label = _iso_volume_label(args.iso)
    initrds: list[Path] = []
    for ucode_key in ("intel_ucode", "amd_ucode"):
        ucode = boot_assets.get(ucode_key)
        if ucode is not None:
            initrds.append(ucode)
    initrds.append(boot_assets["initramfs"])
    cmdline = (
        f"archisobasedir=arch archisolabel={iso_label} "
        "console=ttyS0,115200 console=tty0"
    )

    serial_sock = workspace / "serial.sock"
    if serial_sock.exists():
        serial_sock.unlink()

    qemu_argv = _build_install_qemu_argv(
        iso=args.iso,
        disk=disk,
        workspace=share_dir,
        ovmf_code=args.ovmf_code,
        ovmf_vars=args.ovmf_vars,
        monitor_sock=monitor_sock,
        serial_sock=serial_sock,
        use_kvm=not args.no_kvm,
        memory_mib=args.memory_mib,
        cpus=args.cpus,
        display=args.display,
        kernel=boot_assets["vmlinuz"],
        initrds=tuple(initrds),
        cmdline=cmdline,
    )
    print("[qemu_smoke] install phase:", " ".join(qemu_argv), flush=True)
    proc = subprocess.Popen(qemu_argv)
    monitor = _QemuMonitor(monitor_sock)
    serial_port = _SerialPort(serial_sock, serial_log)
    exit_code = 3
    rc: int | None = None
    boot_serial_log = workspace / "serial-boot.log"
    try:
        monitor.connect(timeout=60.0)
        serial_port.connect(timeout=60.0)
        rc = _drive_install(
            serial_port, serial_log=serial_log, workspace=share_dir,
        )
    except RuntimeError as exc:
        print(f"[qemu_smoke] orchestration error: {exc}", file=sys.stderr)
        exit_code = 3
    finally:
        serial_port.close()
        monitor.quit()
        monitor.close()
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)

    if rc is None:
        # Orchestration error already reported; jump to log copy.
        pass
    elif rc != 0:
        print(f"[qemu_smoke] install exited rc={rc}", file=sys.stderr)
        exit_code = 1
    elif args.reboot_check:
        if _verify_disk_boot(
            disk=disk,
            ovmf_code=args.ovmf_code,
            ovmf_vars=args.ovmf_vars,
            workspace=workspace,
            serial_log=boot_serial_log,
            use_kvm=not args.no_kvm,
            memory_mib=args.memory_mib,
            cpus=args.cpus,
            display=args.display,
        ):
            exit_code = 0
        else:
            print(
                "[qemu_smoke] installed system did not boot cleanly",
                file=sys.stderr,
            )
            exit_code = 2
    else:
        exit_code = 0

    # Always copy logs out for CI artifact upload.
    log_dir = Path(os.environ.get("QEMU_SMOKE_LOG_DIR", str(workspace / "logs")))
    log_dir.mkdir(parents=True, exist_ok=True)
    for source in (
        serial_log,
        boot_serial_log,
        share_dir / "install.log",
        share_dir / "install.exit",
    ):
        if source.is_file():
            shutil.copy2(source, log_dir / source.name)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
