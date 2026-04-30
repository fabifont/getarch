"""Versioned config schemas. Currently only v1 exists."""

from getarch.config.schema.v1 import Config as ConfigV1

LATEST = ConfigV1

__all__ = ["LATEST", "ConfigV1"]
