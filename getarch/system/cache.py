"""Short-lived on-disk cache for idempotent discovery commands.

Keyed by the command's argv tuple so two consecutive ``getarch
discover`` / ``validate`` / ``plan`` invocations on the same ISO boot
re-use the cached output of ``lsblk``, ``localectl``, etc., instead of
re-spawning a subprocess. TTL defaults to 60 seconds, configurable via
``GETARCH_DISCOVERY_TTL``.

The cache directory is purely ephemeral — nothing in it is needed for
correctness; deleting it just forces a refresh.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_DEFAULT_TTL_SECONDS: Final[int] = 60
_TTL_ENV: Final[str] = "GETARCH_DISCOVERY_TTL"


def default_cache_dir() -> Path:
    """Honour ``XDG_CACHE_HOME`` then fall back to ``~/.cache/getarch``."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "getarch"


def resolved_ttl_seconds() -> int:
    raw = os.environ.get(_TTL_ENV)
    if raw is None:
        return _DEFAULT_TTL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_TTL_SECONDS
    return max(value, 0)


@dataclass(slots=True)
class TimedCache:
    """Filesystem-backed cache: one JSON file per argv tuple."""

    root: Path
    ttl_seconds: int = _DEFAULT_TTL_SECONDS

    def get(self, argv: Iterable[str]) -> str | None:
        path = self._path_for(tuple(argv))
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        ts = payload.get("ts")
        stdout = payload.get("stdout")
        if not isinstance(ts, (int, float)) or not isinstance(stdout, str):
            return None
        if time.time() - float(ts) > self.ttl_seconds:
            return None
        return stdout

    def put(self, argv: Iterable[str], stdout: str) -> None:
        path = self._path_for(tuple(argv))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps({"ts": time.time(), "stdout": stdout}),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError:
            # The cache is best-effort; a full disk shouldn't break
            # discovery itself.
            return

    def clear(self) -> None:
        if not self.root.is_dir():
            return
        for entry in self.root.glob("*.json"):
            try:
                entry.unlink()
            except OSError:
                continue

    def _path_for(self, argv: tuple[str, ...]) -> Path:
        # Argv is normalised into a stable filename. Sanitise so we
        # never accidentally write outside the cache root: only the
        # first token (the binary basename) becomes the human-readable
        # prefix; the rest is hashed into a digest segment.
        import hashlib  # noqa: PLC0415

        head = Path(argv[0]).name if argv else "empty"
        safe_head = "".join(ch if ch.isalnum() or ch in "-_." else "_"
                            for ch in head)[:32] or "cmd"
        digest = hashlib.sha256(
            "\x00".join(argv).encode("utf-8"),
        ).hexdigest()[:16]
        return self.root / f"{safe_head}-{digest}.json"
