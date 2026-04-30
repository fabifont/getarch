"""Identity discovery: who is running getarch."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OsIdentity:
    def is_root(self) -> bool:
        return os.geteuid() == 0
