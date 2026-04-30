"""`getarch discover` - inspect ISO environment."""

from __future__ import annotations

import json
import sys

import click

from getarch.cli.output import GetarchConsole
from getarch.execution.real_runner import RealRunner
from getarch.system.block_devices import LsblkBlockDevices
from getarch.system.environment import IsoEnvironment
from getarch.system.firmware import EfivarsFirmware


def _discover() -> dict[str, object]:
    runner = RealRunner()
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


def run() -> None:
    ctx = click.get_current_context()
    obj: dict[str, object] = ctx.obj or {}
    info = _discover()
    if obj.get("json_mode"):
        sys.stdout.write(json.dumps(info, indent=2) + "\n")
        return
    console = GetarchConsole(json_mode=False, no_color=bool(obj.get("no_color")))
    console.log(info)
