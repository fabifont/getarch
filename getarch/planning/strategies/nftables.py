"""nftables ruleset rendering.

Each entry in ``cfg.network.firewall_nftables_rules`` is a complete rule
written verbatim under ``table inet getarch { … }`` in
``/etc/nftables.conf``. The strategy installs the package via the
existing packages step (planner adds ``nftables`` automatically when
rules are non-empty) and enables ``nftables.service`` via the existing
services step (likewise auto-enabled).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from getarch.execution.command import Command


@dataclass(frozen=True, slots=True)
class NftablesStrategy:
    rules: tuple[str, ...]
    mount_root: Path

    def commands(self) -> tuple[Command, ...]:
        if not self.rules:
            return ()
        target = self.mount_root / "etc/nftables.conf"
        body = "\n".join(f"  {line}" for line in self.rules)
        text = (
            "#!/usr/sbin/nft -f\n"
            "flush ruleset\n"
            "\n"
            "table inet getarch {\n"
            f"{body}\n"
            "}\n"
        )
        return (
            Command(
                argv=("install", "-Dm644", "/dev/stdin", str(target)),
                input=text,
                description=f"write {target}",
            ),
        )
