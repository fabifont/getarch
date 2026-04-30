from pathlib import Path

from getarch.planning.strategies.mirrors import (
    ReflectorStrategy,
    StaticMirrorlistStrategy,
    build_mirror_strategy,
)


def test_reflector_emits_save_command() -> None:
    strat = ReflectorStrategy(
        args=("--country", "Italy", "--protocol", "https"),
        mount_root=Path("/mnt"),
    )
    cmds = strat.commands()
    assert len(cmds) == 1
    assert cmds[0].argv == (
        "reflector",
        "--save",
        "/etc/pacman.d/mirrorlist",
        "--country",
        "Italy",
        "--protocol",
        "https",
    )


def test_static_emits_install_command() -> None:
    strat = StaticMirrorlistStrategy(
        static_path=Path("/etc/foo/mirrorlist"),
        mount_root=Path("/mnt"),
    )
    cmds = strat.commands()
    assert len(cmds) == 1
    assert cmds[0].argv == (
        "install",
        "-Dm644",
        "/etc/foo/mirrorlist",
        "/etc/pacman.d/mirrorlist",
    )


class _Mirrors:
    def __init__(
        self,
        *,
        strategy: str = "keep",
        reflector_args: tuple[str, ...] = (),
        static_path: str | None = None,
    ) -> None:
        self.strategy = strategy
        self.reflector_args = list(reflector_args)
        self.static_path = static_path


def test_build_returns_none_for_keep() -> None:
    assert build_mirror_strategy(_Mirrors(strategy="keep"), Path("/mnt")) is None


def test_build_returns_reflector() -> None:
    out = build_mirror_strategy(
        _Mirrors(strategy="reflector", reflector_args=("--latest", "20")),
        Path("/mnt"),
    )
    assert isinstance(out, ReflectorStrategy)


def test_build_returns_static() -> None:
    out = build_mirror_strategy(
        _Mirrors(strategy="static", static_path="/etc/mirrorlist"),
        Path("/mnt"),
    )
    assert isinstance(out, StaticMirrorlistStrategy)
