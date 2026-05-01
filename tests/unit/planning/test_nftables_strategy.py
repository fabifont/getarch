from copy import deepcopy
from pathlib import Path

from getarch.config.examples import EXAMPLES
from getarch.config.schema.v1 import Config
from getarch.domain.disk import Disk, DiskPath
from getarch.planning.planner import Planner
from getarch.planning.strategies.nftables import NftablesStrategy


def test_strategy_renders_rules_under_table_inet_getarch() -> None:
    cmds = NftablesStrategy(
        rules=(
            "chain input { type filter hook input priority 0; drop }",
            "chain output { type filter hook output priority 0; accept }",
        ),
        mount_root=Path("/mnt"),
    ).commands()
    assert len(cmds) == 1
    cmd = cmds[0]
    assert cmd.argv[-1] == "/mnt/etc/nftables.conf"
    body = cmd.input or ""
    assert "table inet getarch {" in body
    assert "chain input" in body
    assert "chain output" in body
    assert body.startswith("#!/usr/sbin/nft -f\n")


def test_empty_rules_emit_no_commands() -> None:
    assert NftablesStrategy(rules=(), mount_root=Path("/mnt")).commands() == ()


def test_planner_adds_nftables_package_and_enables_service() -> None:
    payload = deepcopy(EXAMPLES["minimal-ext4"])
    payload["network"] = {
        "hostname": "h",
        "firewall_nftables_rules": [
            "chain input { type filter hook input priority 0; drop }",
        ],
    }
    cfg = Config.model_validate(payload)
    plan = Planner().build(
        cfg=cfg,
        disk=Disk(path=DiskPath(Path("/dev/sda")), size_bytes=2**40),
        mount_root=Path("/mnt"),
    )
    pkgs_step = next(s for s in plan.steps if s.id == "packages")
    pacstrap_argv = pkgs_step.commands[0].argv
    assert "nftables" in pacstrap_argv
    services = next(s for s in plan.steps if s.id == "services")
    flat = " ".join(arg for c in services.commands for arg in c.argv)
    assert "nftables" in flat
    assert "nftables" in {s.id for s in plan.steps}
