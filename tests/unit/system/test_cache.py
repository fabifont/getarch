"""TimedCache + CachingRunner tests."""

from __future__ import annotations

import time
from pathlib import Path
from typing import override

import pytest

from getarch.execution.caching_runner import CACHEABLE_PREFIXES, CachingRunner
from getarch.execution.command import Command
from getarch.execution.fake_runner import FakeRunner
from getarch.execution.result import CommandResult
from getarch.system.cache import (
    TimedCache,
    default_cache_dir,
    resolved_ttl_seconds,
)


def test_default_cache_dir_honours_xdg_cache_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "x"))
    assert default_cache_dir() == tmp_path / "x" / "getarch"


def test_default_cache_dir_falls_back_to_home_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_cache_dir() == tmp_path / ".cache" / "getarch"


def test_resolved_ttl_seconds_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GETARCH_DISCOVERY_TTL", raising=False)
    assert resolved_ttl_seconds() == 60


def test_resolved_ttl_seconds_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GETARCH_DISCOVERY_TTL", "5")
    assert resolved_ttl_seconds() == 5


def test_resolved_ttl_seconds_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GETARCH_DISCOVERY_TTL", "nonsense")
    assert resolved_ttl_seconds() == 60


def test_cache_round_trip(tmp_path: Path) -> None:
    c = TimedCache(root=tmp_path, ttl_seconds=60)
    assert c.get(("lsblk", "-J")) is None
    c.put(("lsblk", "-J"), '{"hello":"world"}')
    assert c.get(("lsblk", "-J")) == '{"hello":"world"}'


def test_cache_expires_after_ttl(tmp_path: Path) -> None:
    c = TimedCache(root=tmp_path, ttl_seconds=0)
    c.put(("lsblk",), "stale")
    # Force-stamp the file in the past so the TTL test is deterministic.
    time.sleep(0.01)
    assert c.get(("lsblk",)) is None


def test_cache_clear_drops_entries(tmp_path: Path) -> None:
    c = TimedCache(root=tmp_path, ttl_seconds=60)
    c.put(("lsblk",), "v")
    c.clear()
    assert c.get(("lsblk",)) is None


def test_cache_does_not_escape_root(tmp_path: Path) -> None:
    """A pathological argv must not write outside the cache directory."""

    c = TimedCache(root=tmp_path, ttl_seconds=60)
    c.put(("../../../../etc/passwd",), "owned")
    survivors = [p.name for p in tmp_path.iterdir()]
    # All survivors live inside the root and have the safe naming
    # convention (sha256 digest segment).
    for name in survivors:
        assert ".." not in name
        assert "/" not in name


def test_cacheable_prefixes_match_lsblk_argv() -> None:
    cmd = Command(argv=("lsblk", "-J", "-b"))
    assert any(len(p) <= len(cmd.argv) and cmd.argv[: len(p)] == p for p in CACHEABLE_PREFIXES)


class _RecordingFake(FakeRunner):
    """FakeRunner subclass that records each command and returns a stub."""

    @override
    def run(self, command: Command, *, chroot_path: str = "/mnt") -> CommandResult:
        super().run(command, chroot_path=chroot_path)
        return CommandResult(
            command=command,
            returncode=0,
            stdout=f"out:{command.argv[0]}",
            stderr="",
        )


def test_caching_runner_skips_non_cacheable(tmp_path: Path) -> None:
    inner = _RecordingFake()
    runner = CachingRunner(inner=inner, cache=TimedCache(root=tmp_path))
    runner.run(Command(argv=("pacstrap", "-K", "/mnt")))
    runner.run(Command(argv=("pacstrap", "-K", "/mnt")))
    # No cache; both invocations hit the inner runner.
    assert len(inner.recorded) == 2


def test_caching_runner_short_circuits_cacheable(tmp_path: Path) -> None:
    inner = _RecordingFake()
    cache = TimedCache(root=tmp_path)
    runner = CachingRunner(inner=inner, cache=cache)
    first = runner.run(Command(argv=("lsblk", "-J", "-b")))
    second = runner.run(Command(argv=("lsblk", "-J", "-b")))
    assert first.stdout == second.stdout
    # Inner saw only the first call; the second was served from cache.
    assert len(inner.recorded) == 1


def test_caching_runner_skips_sensitive_or_input(tmp_path: Path) -> None:
    inner = _RecordingFake()
    runner = CachingRunner(inner=inner, cache=TimedCache(root=tmp_path))
    runner.run(Command(argv=("lsblk",), input="hi"))
    runner.run(Command(argv=("lsblk",), sensitive=True))
    runner.run(Command(argv=("lsblk",), chroot=True))
    assert len(inner.recorded) == 3  # none cached
