"""Hardware quirks database.

Each quirk is a small YAML file under ``getarch/quirks/`` describing:

* an opaque ``id`` the user opts into via ``cfg.quirks.enable``,
* a ``match`` block (currently ``pci_subsystem: "<vendor>:<device>"``),
* zero or more ``modules`` (added to the mkinitcpio ``MODULES=()``
  array) and ``cmdline`` (appended to the bootloader cmdline).

Loading is one-shot at import; matching is done against the lspci
output collected at preflight time.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

from getarch.execution.command import Command
from getarch.execution.runner import CommandRunner

_QUIRKS_DIR_DEFAULT: Path = Path(__file__).resolve().parent.parent / "quirks"
_PCI_LINE = re.compile(
    r'^[\da-f]{2}:[\da-f]{2}\.\d "[^"]*" "([\da-f]{4})" "([\da-f]{4})"',
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Quirk:
    id: str
    description: str
    match_pci: str | None
    modules: tuple[str, ...]
    cmdline: tuple[str, ...]


@dataclass(slots=True)
class QuirkRegistry:
    quirks: list[Quirk] = field(default_factory=list)

    @classmethod
    def load_default(cls, root: Path | None = None) -> QuirkRegistry:
        return cls.load_from(root or _QUIRKS_DIR_DEFAULT)

    @classmethod
    def load_from(cls, root: Path) -> QuirkRegistry:
        registry = cls()
        if not root.is_dir():
            return registry
        for entry in sorted(root.glob("*.yaml")):
            loaded: object = yaml.safe_load(entry.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                continue
            payload = cast("dict[str, object]", loaded)
            match_obj = payload.get("match")
            pci_obj: object = ""
            if isinstance(match_obj, dict):
                pci_obj = cast("dict[str, object]", match_obj).get(
                    "pci_subsystem", "",
                )
            modules_obj = payload.get("modules", [])
            cmdline_obj = payload.get("cmdline", [])
            modules_list: list[object] = (
                cast("list[object]", modules_obj)
                if isinstance(modules_obj, list)
                else []
            )
            cmdline_list: list[object] = (
                cast("list[object]", cmdline_obj)
                if isinstance(cmdline_obj, list)
                else []
            )
            registry.quirks.append(
                Quirk(
                    id=str(payload["id"]),
                    description=str(payload.get("description", "")),
                    match_pci=str(pci_obj) if pci_obj else None,
                    modules=tuple(str(m) for m in modules_list),
                    cmdline=tuple(str(c) for c in cmdline_list),
                ),
            )
        return registry

    def find_matches(self, pci_ids: Iterable[str]) -> tuple[Quirk, ...]:
        seen = {pid.lower() for pid in pci_ids}
        return tuple(
            q for q in self.quirks
            if q.match_pci and q.match_pci.lower() in seen
        )

    def by_id(self, qid: str) -> Quirk | None:
        for q in self.quirks:
            if q.id == qid:
                return q
        return None


def lspci_pci_ids(runner: CommandRunner) -> tuple[str, ...]:
    """Return ``vendor:device`` pairs from ``lspci -nn -mm`` output.

    The ``-mm`` mode emits a parser-friendly format:
    ``00:1f.6 "Ethernet controller" "8086" "1539" -r02 ...``.
    """
    result = runner.run(Command(argv=("lspci", "-nn", "-mm")))
    if not result.ok:
        return ()
    pairs: list[str] = []
    for line in result.stdout.splitlines():
        m = _PCI_LINE.match(line)
        if m:
            pairs.append(f"{m.group(1).lower()}:{m.group(2).lower()}")
    return tuple(pairs)
