"""Mirrorlist strategies: reflector or static copy.

Both strategies write to ``/etc/pacman.d/mirrorlist`` on the live ISO so
``pacstrap`` picks the new mirrors up. ``pacstrap -K`` later copies the
resolved mirrorlist into the target system; nothing additional is needed
inside the chroot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from getarch.execution.command import Command


class _MirrorsConfigLike(Protocol):
    @property
    def strategy(self) -> str: ...
    @property
    def reflector_args(self) -> list[str]: ...
    @property
    def static_path(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class ReflectorStrategy:
    args: tuple[str, ...]
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        return (
            Command(
                argv=(
                    "reflector",
                    "--save",
                    "/etc/pacman.d/mirrorlist",
                    *self.args,
                ),
                description=("run reflector to update the live ISO mirrorlist before pacstrap"),
            ),
        )


@dataclass(frozen=True, slots=True)
class StaticMirrorlistStrategy:
    static_path: Path
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        return (
            Command(
                argv=(
                    "install",
                    "-Dm644",
                    str(self.static_path),
                    "/etc/pacman.d/mirrorlist",
                ),
                description=(
                    f"copy {self.static_path} to /etc/pacman.d/mirrorlist before pacstrap"
                ),
            ),
        )


def build_mirror_strategy(
    cfg_mirrors: _MirrorsConfigLike,
    mount_root: Path,
) -> ReflectorStrategy | StaticMirrorlistStrategy | None:
    if cfg_mirrors.strategy == "keep":
        return None
    if cfg_mirrors.strategy == "reflector":
        return ReflectorStrategy(
            args=tuple(cfg_mirrors.reflector_args),
            mount_root=mount_root,
        )
    if cfg_mirrors.strategy == "static":
        if not cfg_mirrors.static_path:
            raise ValueError("static_path required for static mirror strategy")
        return StaticMirrorlistStrategy(
            static_path=Path(cfg_mirrors.static_path),
            mount_root=mount_root,
        )
    raise ValueError(f"unknown mirrors strategy: {cfg_mirrors.strategy!r}")
