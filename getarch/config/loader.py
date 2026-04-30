"""Config file loader. Today: JSON only. YAML/TOML would slot in here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from getarch.config.schema.v1 import Config as ConfigV1
from getarch.errors import SyntacticConfigError


def load_config(path: Path) -> ConfigV1:
    """Load and validate a config file at ``path``."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SyntacticConfigError(f"config file not found: {path}") from exc
    except OSError as exc:
        raise SyntacticConfigError(f"unable to read config: {exc}") from exc

    try:
        raw: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SyntacticConfigError(f"config is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise SyntacticConfigError("config root must be an object")

    payload: dict[str, Any] = raw  # type: ignore[assignment]
    version = payload.get("version")
    if version != 1:
        raise SyntacticConfigError(
            f"unsupported config version {version!r}; supported: 1",
        )
    try:
        return ConfigV1.model_validate(payload)
    except ValidationError as exc:
        raise SyntacticConfigError(str(exc)) from exc
