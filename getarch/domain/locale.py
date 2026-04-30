"""Locale-related value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HOSTNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
_TIMEZONE_RE = re.compile(r"^[A-Za-z]+(?:/[A-Za-z0-9_+\-]+)*$")


@dataclass(frozen=True, slots=True)
class Hostname:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not _HOSTNAME_RE.match(self.value):
            raise ValueError(f"invalid hostname: {self.value!r}")


@dataclass(frozen=True, slots=True)
class Locale:
    """A line for /etc/locale.gen, e.g. 'en_US.UTF-8 UTF-8'."""

    line: str

    def __post_init__(self) -> None:
        if not self.line or len(self.line.split()) < 2:  # noqa: PLR2004 — needs lang + charset
            raise ValueError(f"locale must include a charset: {self.line!r}")

    @property
    def lang(self) -> str:
        return self.line.split()[0]


@dataclass(frozen=True, slots=True)
class Keymap:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("keymap name must not be empty")


@dataclass(frozen=True, slots=True)
class Timezone:
    name: str

    def __post_init__(self) -> None:
        if not _TIMEZONE_RE.match(self.name):
            raise ValueError(f"invalid timezone: {self.name!r}")
