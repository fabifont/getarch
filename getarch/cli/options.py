"""Shared CLI options (log level, output mode)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    json_mode: bool
    no_color: bool
    log_level: str
    verbose: bool
    debug: bool
