"""lsblk-backed block device discovery (JSON-mode parsing)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from getarch.domain.disk import Disk, DiskPath
from getarch.errors import DiscoveryError
from getarch.execution.command import Command
from getarch.execution.runner import CommandRunner


@dataclass(slots=True)
class LsblkBlockDevices:
    runner: CommandRunner

    def list_disks(self) -> tuple[Disk, ...]:
        result = self.runner.run(
            Command(argv=("lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MODEL"))
        )
        try:
            data: Any = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DiscoveryError(f"lsblk output is not JSON: {exc}") from exc
        devices = data.get("blockdevices", [])
        disks: list[Disk] = []
        for entry in devices:
            if entry.get("type") != "disk":
                continue
            name = entry.get("name")
            size = int(entry.get("size", 0) or 0)
            if not name or size <= 0:
                continue
            model = entry.get("model")
            disks.append(
                Disk(
                    path=DiskPath(Path(f"/dev/{name}")),
                    size_bytes=size,
                    model=model.strip() if isinstance(model, str) else None,
                ),
            )
        return tuple(disks)
