"""getarch config schema, version 2.

For now v2 is a *routing* placeholder: it re-exports the v1 model so
downstream code keeps working unchanged. The first real divergence
will happen when the schema needs a backwards-incompatible change
that warrants a major bump.

Adding a v2-only field today would invalidate every existing v1
config silently — the migration in :mod:`getarch.config.migrations`
exists so that, when v2 *does* diverge, users have a deterministic
path to upgrade.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator

from getarch.config.schema.v1 import Config as ConfigV1


class Config(ConfigV1):
    """v2 config — currently identical to v1 except the version literal."""

    version: Literal[2]  # type: ignore[assignment]

    @field_validator("version", mode="before")
    @classmethod
    def _coerce_version(cls, value: object) -> object:
        # Pydantic accepts both 2 and "2" but Literal demands the int.
        if value == "2":
            return 2
        return value
