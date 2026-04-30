"""Arch ISO detection by reading /etc/os-release."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OsReleaseIso:
    path: Path = Path("/etc/os-release")

    def is_arch_iso(self) -> bool:
        if not self.path.is_file():
            return False
        fields = self._parse(self.path.read_text(encoding="utf-8"))
        return fields.get("ID") == "arch" and "IMAGE_ID" in fields

    @staticmethod
    def _parse(text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            out[key.strip()] = value
        return out
