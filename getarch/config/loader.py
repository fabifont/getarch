"""Config file loader. Supports JSON, YAML, and TOML by file extension."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from getarch.config.schema.v1 import Config as ConfigV1
from getarch.errors import SyntacticConfigError

_YAML_SUFFIXES = frozenset({".yaml", ".yml"})
_TOML_SUFFIXES = frozenset({".toml"})
_JSON_SUFFIXES = frozenset({".json"})


def load_config(path: Path) -> ConfigV1:
    """Load and validate a config file at ``path``."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SyntacticConfigError(f"config file not found: {path}") from exc
    except OSError as exc:
        raise SyntacticConfigError(f"unable to read config: {exc}") from exc

    raw = _parse(path, text)
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


def _parse(path: Path, text: str) -> object:
    suffix = path.suffix.lower()
    if suffix in _YAML_SUFFIXES:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SyntacticConfigError(f"config is not valid YAML: {exc}") from exc
    if suffix in _TOML_SUFFIXES:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise SyntacticConfigError(f"config is not valid TOML: {exc}") from exc
    if suffix in _JSON_SUFFIXES or not suffix:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SyntacticConfigError(f"config is not valid JSON: {exc}") from exc
    raise SyntacticConfigError(
        f"unsupported config file extension {suffix!r}; "
        "use .json, .yaml/.yml, or .toml",
    )
