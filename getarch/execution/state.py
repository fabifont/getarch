"""On-disk pipeline state for ``--resume`` after a failed step.

The state file lives at ``<mount>/var/log/getarch.state.json`` so it
survives a reboot of the live ISO without being part of the new system's
permanent state. It records the IDs of the steps that completed
successfully, the schema version, and the last error if any.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_SCHEMA_VERSION = 1
_DEFAULT_FILENAME = "getarch.state.json"


@dataclass(slots=True)
class PipelineState:
    completed: list[str] = field(default_factory=list)
    last_error: str | None = None
    schema_version: int = _SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "completed": list(self.completed),
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PipelineState:
        version = payload.get("schema_version")
        if version != _SCHEMA_VERSION:
            raise ValueError(
                f"unsupported pipeline state schema_version {version!r} "
                f"(expected {_SCHEMA_VERSION})",
            )
        completed_raw = payload.get("completed")
        if not isinstance(completed_raw, list):
            raise TypeError("pipeline state.completed must be a list")
        completed: list[str] = [str(item) for item in completed_raw]  # type: ignore[unknown-arg-type]
        last_error_raw = payload.get("last_error")
        last_error = str(last_error_raw) if isinstance(last_error_raw, str) else None
        return cls(
            completed=completed,
            last_error=last_error,
            schema_version=_SCHEMA_VERSION,
        )

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def read(cls, path: Path) -> PipelineState:
        text = path.read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))


def default_state_path(mount_root: Path) -> Path:
    return mount_root / "var/log" / _DEFAULT_FILENAME
