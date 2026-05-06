"""`getarch discover` - inspect ISO environment."""

from __future__ import annotations

import json
import sys

import click
import typer

from getarch.cli.output import GetarchConsole
from getarch.execution.caching_runner import CachingRunner
from getarch.execution.real_runner import RealRunner
from getarch.execution.runner import CommandRunner
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.cache import (
    TimedCache,
    default_cache_dir,
    resolved_ttl_seconds,
)
from getarch.system.environment import IsoEnvironment
from getarch.system.firmware import EfivarsFirmware


def build_discovery_runner(*, no_cache: bool = False) -> CommandRunner:
    """Wrap :class:`RealRunner` with a :class:`CachingRunner` unless disabled."""
    inner: CommandRunner = RealRunner()
    if no_cache:
        return inner
    cache = TimedCache(
        root=default_cache_dir(),
        ttl_seconds=resolved_ttl_seconds(),
    )
    return CachingRunner(inner=inner, cache=cache)


def _discover(runner: CommandRunner) -> dict[str, object]:
    bd = LsblkBlockDevices(runner=runner)
    env = IsoEnvironment(runner=runner)
    fw = EfivarsFirmware()
    disks = bd.list_disks()
    locales = env.supported_locales()
    keymaps = env.keymaps()
    timezones = env.timezones()
    return {
        "disks": [
            {"path": d.path.as_posix(), "size_bytes": d.size_bytes, "model": d.model} for d in disks
        ],
        "uefi": fw.is_uefi(),
        "cpu_vendor": env.cpu_vendor(),
        "locales_count": len(locales),
        "keymaps_count": len(keymaps),
        "timezones_count": len(timezones),
    }


def run(
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Skip the discovery cache (always re-run lsblk/localectl/...).",
    ),
    clear_cache: bool = typer.Option(
        False,
        "--clear-cache",
        help="Drop the cache before running discovery.",
    ),
) -> None:
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    if clear_cache:
        TimedCache(
            root=default_cache_dir(),
            ttl_seconds=resolved_ttl_seconds(),
        ).clear()
    runner = build_discovery_runner(no_cache=no_cache)
    info = _discover(runner)
    if obj.get("json_mode"):
        sys.stdout.write(json.dumps(info, indent=2) + "\n")
        return
    console = GetarchConsole(json_mode=False, no_color=bool(obj.get("no_color")))
    console.log(info)
