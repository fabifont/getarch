"""Firmware/UEFI detection by checking efivars presence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.constants import EFIVARS_DIR


@dataclass(frozen=True, slots=True)
class EfivarsFirmware:
    efivars_dir: Path = EFIVARS_DIR

    def is_uefi(self) -> bool:
        return self.efivars_dir.is_dir() and any(self.efivars_dir.iterdir())
