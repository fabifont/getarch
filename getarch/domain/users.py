"""User-related value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from getarch.domain.secret import Secret

_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")


@dataclass(frozen=True, slots=True)
class Username:
    value: str

    def __post_init__(self) -> None:
        if not _USERNAME_RE.match(self.value):
            raise ValueError(f"invalid username: {self.value!r}")


@dataclass(frozen=True, slots=True)
class UserSpec:
    username: Username
    password: Secret | None = None
    groups: tuple[str, ...] = field(default_factory=tuple)
    shell: str = "/bin/bash"
    create_home: bool = True
    sudo: bool = False


class RootAuthKind(StrEnum):
    PROMPT = "prompt"
    PLAIN = "plain"
    HASHED = "hashed"
    SECRET_FILE = "secret-file"  # noqa: S105 — enum tag, not a hardcoded password


@dataclass(frozen=True, slots=True)
class RootAuth:
    kind: RootAuthKind = RootAuthKind.PROMPT
    plain: Secret | None = None
    hashed: str | None = None
    secret_file: str | None = None

    def __post_init__(self) -> None:
        match self.kind:
            case RootAuthKind.PLAIN:
                if self.plain is None:
                    raise ValueError("RootAuth(kind=plain) requires a plain password")
            case RootAuthKind.HASHED:
                if not self.hashed:
                    raise ValueError("RootAuth(kind=hashed) requires the hashed value")
            case RootAuthKind.SECRET_FILE:
                if not self.secret_file:
                    raise ValueError("RootAuth(kind=secret-file) requires a path")
            case RootAuthKind.PROMPT:
                pass
