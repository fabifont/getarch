"""`getarch schema` - emit the v1 JSON schema."""

from __future__ import annotations

import json
import sys

from getarch.config.schema.v1 import Config


def run() -> None:
    sys.stdout.write(json.dumps(Config.model_json_schema(), indent=2) + "\n")
