"""Environment discovery: CPU vendor, locales, keymaps, timezones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command
from getarch.execution.runner import CommandRunner


@dataclass(slots=True)
class IsoEnvironment:
    runner: CommandRunner
    cpuinfo_path: Path = Path("/proc/cpuinfo")
    locales_path: Path = Path("/usr/share/i18n/SUPPORTED")

    def cpu_vendor(self) -> str | None:
        if not self.cpuinfo_path.exists():
            return None
        for line in self.cpuinfo_path.read_text().splitlines():
            if line.startswith("vendor_id"):
                _, _, value = line.partition(":")
                return value.strip() or None
        return None

    def supported_locales(self) -> tuple[str, ...]:
        if not self.locales_path.exists():
            return ()
        out: list[str] = []
        for raw in self.locales_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
        return tuple(out)

    def keymaps(self) -> tuple[str, ...]:
        result = self.runner.run(Command(argv=("localectl", "list-keymaps")))
        return tuple(line for line in result.stdout.splitlines() if line.strip())

    def timezones(self) -> tuple[str, ...]:
        result = self.runner.run(Command(argv=("timedatectl", "list-timezones")))
        return tuple(line for line in result.stdout.splitlines() if line.strip())
